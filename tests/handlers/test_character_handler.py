#!/usr/bin/env python3
# tests/test_character_handler.py

import asyncio
import pytest
from chuk_protocol_server.handlers.character_handler import (
    CharacterHandler,
    CRLF,
    ERASE_CHAR,
)
from chuk_protocol_server.handlers.base_handler import BaseHandler

# Dummy implementations for the reader and writer
class DummyReader:
    def __init__(self, data: bytes = b''):
        self.data = data
        self.read_called = False

    async def read(self, n: int = -1) -> bytes:
        self.read_called = True
        # Return data and then clear it to simulate end-of-data
        result = self.data[:n] if n != -1 else self.data
        self.data = b""
        return result

class DummyWriter:
    def __init__(self):
        self.data = []
        self.closed = False
        self.extra_info = {'peername': ('127.0.0.1', 1234)}
        self.write_called = False

    def write(self, data: bytes):
        self.write_called = True
        self.data.append(data)
        return None

    async def drain(self):
        pass

    def get_extra_info(self, name: str, default=None):
        return self.extra_info.get(name, default)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.closed = True

# Dummy subclass of CharacterHandler that uses default_process_character
class DummyCharacterHandler(CharacterHandler):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__(reader, writer)
        self.submitted_command = None  # Record last submitted command

    async def process_character(self, char: str) -> bool:
        # For testing, use the built-in default_process_character
        return await self.default_process_character(char)

    async def on_command_submitted(self, command: str) -> None:
        # Record the command and echo it
        self.submitted_command = command
        await self.send_line(f"Echo: {command}")

@pytest.fixture
def dummy_connection(event_loop):
    reader = DummyReader()
    writer = DummyWriter()
    handler = DummyCharacterHandler(reader, writer)
    return handler, reader, writer

@pytest.mark.asyncio
async def test_send_welcome(dummy_connection):
    handler, _, writer = dummy_connection
    # Clear any previous output
    writer.data.clear()
    await handler.send_welcome()
    # Expect a welcome message line and a prompt ("> ")
    # Since send_line appends CRLF, the first message should end with CRLF.
    welcome_line = writer.data[0]
    prompt = writer.data[1]
    assert b"Welcome to Character Mode" in welcome_line
    assert welcome_line.endswith(CRLF)
    assert prompt == b"> "

@pytest.mark.asyncio
async def test_handle_backspace(dummy_connection):
    handler, _, writer = dummy_connection
    # Simulate a command already entered
    handler.current_command = "abc"
    writer.data.clear()
    await handler.handle_backspace()
    # The current_command should now be "ab"
    assert handler.current_command == "ab"
    # The writer should have sent the erase sequence
    assert ERASE_CHAR in writer.data[0]

@pytest.mark.asyncio
async def test_handle_enter_exit(dummy_connection):
    handler, _, writer = dummy_connection
    writer.data.clear()
    # Set current command to an exit command (e.g. "quit")
    handler.current_command = "quit"
    cont = await handler.handle_enter()
    # The session should be ended and processing should stop
    assert handler.session_ended is True
    assert handler.running is False
    # Expect that goodbye message was sent along with a newline (CRLF)
    output = b"".join(writer.data)
    assert b"Goodbye!" in output
    # And handle_enter should return False to indicate termination.
    assert cont is False

@pytest.mark.asyncio
async def test_handle_enter_normal_command(dummy_connection):
    handler, _, writer = dummy_connection
    writer.data.clear()
    # Set a normal command
    handler.current_command = "hello"
    cont = await handler.handle_enter()
    # The session should not be ended
    assert handler.session_ended is False
    assert handler.running is True
    # Expect that the echoed command was sent via on_command_submitted
    output = b"".join(writer.data)
    assert b"You entered:" not in output  # Default on_command_submitted in DummyCharacterHandler echoes "Echo: <command>"
    assert b"Echo: hello" in output
    # And handle_enter returns True to continue
    assert cont is True

@pytest.mark.asyncio
async def test_default_process_character_ctrl_c(dummy_connection):
    handler, _, writer = dummy_connection
    writer.data.clear()
    # Process a Ctrl+C character ("\x03")
    cont = await handler.default_process_character("\x03")
    # Expect that a closing message was sent and processing should stop.
    output = b"".join(writer.data)
    assert b"^C - Closing connection." in output
    assert cont is False

@pytest.mark.asyncio
async def test_default_process_character_regular(dummy_connection):
    handler, _, writer = dummy_connection
    writer.data.clear()
    # Process a regular character (e.g., "x")
    initial_length = len(handler.current_command)
    cont = await handler.default_process_character("x")
    # The character "x" should have been echoed, and current_command updated.
    output = b"".join(writer.data)
    assert b"x" in output
    assert handler.current_command == "x"
    assert cont is True

@pytest.mark.asyncio
async def test_read_character(dummy_connection):
    # Test that read_character correctly decodes a character.
    # Setup DummyReader with a known character.
    reader = DummyReader(b"a")
    writer = DummyWriter()
    handler = DummyCharacterHandler(reader, writer)
    char = await handler.read_character()
    assert char == "a"

@pytest.mark.asyncio
async def test_read_character_invalid_utf8(dummy_connection):
    # Provide invalid UTF-8 bytes and check that the replacement character is returned.
    reader = DummyReader(b"\xff")
    writer = DummyWriter()
    handler = DummyCharacterHandler(reader, writer)
    char = await handler.read_character()
    # The replacement character (�) should be returned.
    assert char == "�"
