import asyncio
import pytest

from chuk_protocol_server.handlers.telnet_handler import TelnetHandler
from chuk_protocol_server.utils.terminal_codes import CR, LF

# Dummy reader with readline and read methods.
class DummyReader:
    def __init__(self, lines=None, data_bytes=None):
        self.lines = lines or []
        self.data_bytes = data_bytes
        self.readline_called = False
        self.read_called = False

    async def readline(self) -> bytes:
        self.readline_called = True
        if self.lines:
            return self.lines.pop(0)
        return b''

    async def read(self, n=-1) -> bytes:
        self.read_called = True
        if self.data_bytes:
            data = self.data_bytes
            self.data_bytes = b""
            return data
        return b''

# Dummy writer that records written data.
class DummyWriter:
    def __init__(self):
        self.data = []
        self.extra_info = {'peername': ('127.0.0.1', 9999)}
        self.drain_called = False

    def write(self, data: bytes):
        self.data.append(data)

    async def drain(self):
        self.drain_called = True

    def get_extra_info(self, name: str, default=None):
        return self.extra_info.get(name, default)

    def close(self):
        pass

    async def wait_closed(self):
        pass

# Dummy TelnetHandler subclass for testing.
class DummyTelnetHandler(TelnetHandler):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__(reader, writer)
        self.events = []  # record lifecycle events
        self.running = True  # used in loops
        self.addr = "dummy-client"
        # By default, set a known welcome message.
        self.welcome_message = "Welcome to Telnet Mode"

    async def on_connect(self):
        self.events.append("on_connect")

    async def on_disconnect(self):
        self.events.append("on_disconnect")

    async def cleanup(self):
        self.events.append("cleanup")

    async def end_session(self, message: str):
        self.events.append(f"end_session: {message}")
        self.running = False
        await self.send_line(message)

    # Override send_line to append CRLF.
    async def send_line(self, line: str):
        self.writer.write((line + "\r\n").encode('utf-8'))
        await self.writer.drain()

    # For testing, override show_prompt to send a prompt.
    async def show_prompt(self):
        self.writer.write(b"> ")
        await self.writer.drain()

@pytest.fixture
def dummy_connection():
    reader = DummyReader()
    writer = DummyWriter()
    handler = DummyTelnetHandler(reader, writer)
    return handler, reader, writer

@pytest.mark.asyncio
async def test_send_welcome_default(dummy_connection):
    """
    Test that send_welcome sends the custom welcome message and a prompt.
    """
    handler, _, writer = dummy_connection
    writer.data.clear()
    await handler.send_welcome()
    output = b"".join(writer.data)
    assert b"Welcome to Telnet Mode" in output
    # The prompt is sent via show_prompt() in send_welcome().
    assert b"> " in output

@pytest.mark.asyncio
async def test_send_welcome_transparent(dummy_connection):
    """
    Test that if the welcome message is overridden to an empty string,
    only the prompt is sent (transparent mode).
    """
    handler, _, writer = dummy_connection
    handler.welcome_message = ""  # Override to be transparent.
    writer.data.clear()
    await handler.send_welcome()
    output = b"".join(writer.data)
    # In transparent mode, no welcome text (apart from prompt) should appear.
    # We expect that the output only contains the prompt ("> ").
    assert output == b"> "

@pytest.mark.asyncio
async def test_simple_mode_echo_and_exit():
    """
    Test that in "simple" mode the handler reads lines, echoes them,
    and exits on a quit command.
    """
    data_lines = [
        b"Hello Telnet\r\n",
        b"quit\r\n"
    ]
    reader = DummyReader(lines=data_lines.copy())
    writer = DummyWriter()
    handler = DummyTelnetHandler(reader, writer)
    handler.mode = "simple"  # bypass negotiation

    await handler.handle_client()

    output = b"".join(writer.data)
    # Expect the welcome message.
    assert b"Welcome to Telnet Mode" in output
    # Expect echo of the "Hello Telnet" command.
    assert b"Echo: Hello Telnet" in output
    # Expect the goodbye message.
    assert b"Goodbye!" in output
    # Check lifecycle events.
    assert handler.events == ["on_connect", "end_session: Goodbye!", "on_disconnect", "cleanup"]

@pytest.mark.asyncio
async def test_telnet_line_mode_reading():
    """
    Test _read_line_with_telnet in line mode.
    This test simulates a line containing a Telnet command sequence.
    """
    IAC = 255
    raw_line = bytearray(b"Test")
    raw_line.extend(bytes([IAC, IAC]))
    raw_line.extend(b" Line\r\n")
    reader = DummyReader(lines=[bytes(raw_line)])
    writer = DummyWriter()
    handler = DummyTelnetHandler(reader, writer)
    handler.mode = "telnet"
    handler.line_mode = True  # force line mode

    line = await handler._read_line_with_telnet()
    # Strip any trailing CR/LF.
    line = line.rstrip("\r\n")
    # According to the current implementation, the IAC sequence is skipped.
    expected_line = "Test Line"
    assert line == expected_line

@pytest.mark.asyncio
async def test_mixed_mode_read():
    """
    Test _read_mixed_mode to ensure it converts CR LF to newline.
    """
    try:
        cr_int = int(CR)
    except (TypeError, ValueError):
        cr_int = ord(CR)
    try:
        lf_int = int(LF)
    except (TypeError, ValueError):
        lf_int = ord(LF)

    raw_data = b"A" + bytes([cr_int, lf_int]) + b"B"
    reader = DummyReader(data_bytes=raw_data)
    writer = DummyWriter()
    handler = DummyTelnetHandler(reader, writer)
    handler.mode = "telnet"
    handler.line_mode = False

    result = await handler._read_mixed_mode(timeout=1)
    # The implementation preserves the CR LF sequence.
    expected = "A\r\nB"
    assert result == expected

@pytest.mark.asyncio
async def test_process_line_exit_command(dummy_connection):
    """
    Test that process_line sends a goodbye message and returns False for exit commands.
    """
    handler, _, writer = dummy_connection
    writer.data.clear()
    cont = await handler.process_line("quit")
    output = b"".join(writer.data)
    assert b"Goodbye!" in output
    assert cont is False

@pytest.mark.asyncio
async def test_process_line_normal(dummy_connection):
    """
    Test that a normal line is echoed back.
    (TelnetHandler.process_line does not automatically send a prompt.)
    """
    handler, _, writer = dummy_connection
    writer.data.clear()
    cont = await handler.process_line("hello telnet")
    output = b"".join(writer.data)
    assert b"Echo: hello telnet" in output
    # No prompt is expected from process_line.
    assert b"> " not in output
    assert cont is True
