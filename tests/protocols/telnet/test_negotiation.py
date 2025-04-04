#!/usr/bin/env python3
# tests/protocols/telnet/test_negotiation.py

import asyncio
import pytest

# --- Dummy Telnet Constants and Helpers (simulate those from constants.py) ---

IAC = 255
DO = 253
DONT = 254
WILL = 251
WONT = 252
SB = 250
SE = 240

OPT_ECHO = 1
OPT_SGA = 3
OPT_TERMINAL = 24
OPT_NAWS = 31
OPT_LINEMODE = 34

TERMINAL_SEND = 1

def get_command_name(cmd):
    mapping = {DO: "DO", DONT: "DONT", WILL: "WILL", WONT: "WONT"}
    return mapping.get(cmd, f"UNKNOWN({cmd})")

def get_option_name(opt):
    mapping = {
        OPT_ECHO: "ECHO",
        OPT_SGA: "SGA",
        OPT_TERMINAL: "TERMINAL",
        OPT_NAWS: "NAWS",
        OPT_LINEMODE: "LINEMODE",
    }
    return mapping.get(opt, f"OPT({opt})")

# --- Import the module under test ---
from chuk_protocol_server.protocols.telnet.negotiation import (
    _async_write,
    send_command,
    send_subnegotiation,
    request_terminal_type,
    send_initial_negotiations,
    parse_negotiation,
    parse_subnegotiation,
    process_negotiation,
)

# --- Dummy StreamWriter for testing _async_write and send functions ---
class DummyStreamWriter:
    def __init__(self):
        self.data = bytearray()
        self.drained = False
        self.closed = False

    def write(self, data: bytes):
        self.data.extend(data)
        # Return a non-coroutine (simulate immediate write)
        return None

    async def drain(self):
        self.drained = True

# --- Dummy OptionManager for process_negotiation ---
class DummyOptionManager:
    def __init__(self):
        self.local = {}
        self.remote = {}
    def set_local_option(self, opt, state):
        self.local[opt] = state
    def set_remote_option(self, opt, state):
        self.remote[opt] = state

# --- Tests for _async_write ---
@pytest.mark.asyncio
async def test_async_write_normal():
    writer = DummyStreamWriter()
    data = b"test"
    await _async_write(writer, data)
    assert writer.data == data
    assert writer.drained is True

# --- Tests for send_command ---
@pytest.mark.asyncio
async def test_send_command():
    writer = DummyStreamWriter()
    await send_command(writer, WILL, OPT_ECHO)
    # Expect: IAC, WILL, OPT_ECHO
    expected = bytes([IAC, WILL, OPT_ECHO])
    assert writer.data == expected

# --- Tests for send_subnegotiation ---
@pytest.mark.asyncio
async def test_send_subnegotiation():
    writer = DummyStreamWriter()
    data = b"hello"
    await send_subnegotiation(writer, OPT_TERMINAL, data)
    # Expected format: IAC SB, option, data, IAC SE
    expected = bytes([IAC, SB, OPT_TERMINAL]) + data + bytes([IAC, SE])
    assert writer.data == expected

# --- Test for request_terminal_type ---
@pytest.mark.asyncio
async def test_request_terminal_type(monkeypatch):
    writer = DummyStreamWriter()
    calls = []
    async def dummy_send_subnegotiation(writer, option, data):
        calls.append((option, data))
    monkeypatch.setattr("chuk_protocol_server.protocols.telnet.negotiation.send_subnegotiation", dummy_send_subnegotiation)
    await request_terminal_type(writer)
    assert len(calls) == 1
    opt, data = calls[0]
    assert opt == OPT_TERMINAL
    # Data should contain TERMINAL_SEND
    assert data == bytes([TERMINAL_SEND])

# --- Test for send_initial_negotiations ---
@pytest.mark.asyncio
async def test_send_initial_negotiations(monkeypatch):
    writer = DummyStreamWriter()
    commands = []
    async def dummy_send_command(writer, command, option):
        commands.append((command, option))
    monkeypatch.setattr("chuk_protocol_server.protocols.telnet.negotiation.send_command", dummy_send_command)
    await send_initial_negotiations(writer)
    # Check that commands were sent in expected order:
    # WILL ECHO, WILL SGA, DO SGA, DO TERMINAL, DO NAWS, WONT LINEMODE
    expected = [
        (WILL, OPT_ECHO),
        (WILL, OPT_SGA),
        (DO, OPT_SGA),
        (DO, OPT_TERMINAL),
        (DO, OPT_NAWS),
        (WONT, OPT_LINEMODE),
    ]
    assert commands == expected

# --- Tests for parse_negotiation ---
def test_parse_negotiation_valid():
    # Valid negotiation: IAC, DO, OPT_SGA
    buf = bytes([IAC, DO, OPT_SGA]) + b"extra"
    cmd, opt, consumed = parse_negotiation(buf)
    assert cmd == DO
    assert opt == OPT_SGA
    assert consumed == 3

def test_parse_negotiation_incomplete():
    # Buffer too short
    buf = bytes([IAC])
    cmd, opt, consumed = parse_negotiation(buf)
    assert cmd is None and opt is None and consumed == 0

def test_parse_negotiation_no_iac():
    buf = b"random data"
    cmd, opt, consumed = parse_negotiation(buf)
    assert cmd is None and opt is None and consumed == 0

# --- Tests for parse_subnegotiation ---
def test_parse_subnegotiation_valid():
    # Valid subnegotiation: IAC SB, OPT_TERMINAL, data, IAC SE
    data = b"testdata"
    buf = bytes([IAC, SB, OPT_TERMINAL]) + data + bytes([IAC, SE]) + b"more"
    opt, subdata, consumed = parse_subnegotiation(buf)
    assert opt == OPT_TERMINAL
    assert subdata == data
    # consumed should be length of (IAC SB OPT_TERMINAL data IAC SE)
    assert consumed == 3 + len(data) + 2

def test_parse_subnegotiation_incomplete():
    # Incomplete: missing IAC SE at end.
    buf = bytes([IAC, SB, OPT_TERMINAL]) + b"partial"
    opt, subdata, consumed = parse_subnegotiation(buf)
    assert opt is None and subdata is None and consumed == 0

# --- Tests for process_negotiation ---
@pytest.mark.asyncio
async def test_process_negotiation_echo_do(monkeypatch):
    writer = DummyStreamWriter()
    option_manager = DummyOptionManager()
    calls = []
    async def dummy_send_command(writer, command, option):
        calls.append((command, option))
    monkeypatch.setattr("chuk_protocol_server.protocols.telnet.negotiation.send_command", dummy_send_command)
    # Test for OPT_ECHO with DO: should send WILL ECHO and set local option True.
    await process_negotiation(asyncio.StreamReader(), writer, DO, OPT_ECHO, option_manager)
    assert calls[0] == (WILL, OPT_ECHO)
    assert option_manager.local.get(OPT_ECHO) is True

@pytest.mark.asyncio
async def test_process_negotiation_linemode_will(monkeypatch):
    writer = DummyStreamWriter()
    option_manager = DummyOptionManager()
    calls = []
    async def dummy_send_command(writer, command, option):
        calls.append((command, option))
    monkeypatch.setattr("chuk_protocol_server.protocols.telnet.negotiation.send_command", dummy_send_command)
    # For LINEMODE with WILL, should respond with DO LINEMODE and set remote option True.
    await process_negotiation(asyncio.StreamReader(), writer, WILL, OPT_LINEMODE, option_manager)
    # Since our function for LINEMODE doesn't call send_command for WILL explicitly,
    # check that the remote option was set to True.
    assert option_manager.remote.get(OPT_LINEMODE) is True

@pytest.mark.asyncio
async def test_process_negotiation_unknown_option(monkeypatch):
    writer = DummyStreamWriter()
    option_manager = DummyOptionManager()
    calls = []
    async def dummy_send_command(writer, command, option):
        calls.append((command, option))
    monkeypatch.setattr("chuk_protocol_server.protocols.telnet.negotiation.send_command", dummy_send_command)
    # Use an unknown option (e.g., 99)
    await process_negotiation(asyncio.StreamReader(), writer, DO, 99, option_manager)
    # For unknown option and DO, it should send WONT for that option.
    assert calls[0] == (WONT, 99)

# --- Dummy OptionManager for testing process_negotiation ---
class DummyOptionManager:
    def __init__(self):
        self.local = {}
        self.remote = {}
    def set_local_option(self, opt, state):
        self.local[opt] = state
    def set_remote_option(self, opt, state):
        self.remote[opt] = state

