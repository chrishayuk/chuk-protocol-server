#!/usr/bin/env python3
# tests/test_line_handler.py

import asyncio
import pytest
from chuk_protocol_server.handlers.line_handler import LineHandler
from chuk_protocol_server.utils.terminal_codes import CRLF

# Dummy reader with a readline method
class DummyReader:
    def __init__(self, lines=None):
        # lines is a list of bytes (each line should end with a newline)
        self.lines = lines or []
        self.readline_called = False

    async def readline(self) -> bytes:
        self.readline_called = True
        if self.lines:
            return self.lines.pop(0)
        return b''

# Dummy writer that records written data
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

# Dummy subclass of LineHandler that implements on_command_submitted to record commands.
class DummyLineHandler(LineHandler):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__(reader, writer)
        self.submitted_command = None

    async def on_command_submitted(self, command: str) -> None:
        self.submitted_command = command
        await self.send_line(f"Echo: {command}")

@pytest.fixture
def dummy_connection(event_loop):
    # Prepare a DummyReader with no lines initially
    reader = DummyReader()
    writer = DummyWriter()
    handler = DummyLineHandler(reader, writer)
    return handler, reader, writer

@pytest.mark.asyncio
async def test_send_welcome(dummy_connection):
    handler, _, writer = dummy_connection
    writer.data.clear()
    await handler.send_welcome()
    # Expect first message is "Welcome to Line Mode" with CRLF appended,
    # and then a prompt ("> ") sent by show_prompt.
    assert writer.data[0].endswith(CRLF)
    assert b"Welcome to Line Mode" in writer.data[0]
    # Check that the prompt was sent
    assert writer.data[1] == b"> "

@pytest.mark.asyncio
async def test_read_line(dummy_connection):
    # Setup a reader with a known line ending with CRLF
    line_text = "Test command"
    reader = DummyReader([f"{line_text}\r\n".encode('utf-8')])
    writer = DummyWriter()
    handler = DummyLineHandler(reader, writer)
    line = await handler.read_line(timeout=1)
    # The line should be decoded and stripped of CRLF
    assert line == line_text
    # Also, the reader's readline should have been called.
    assert reader.readline_called

@pytest.mark.asyncio
async def test_process_line_exit_command(dummy_connection):
    handler, reader, writer = dummy_connection
    writer.data.clear()
    # Provide an exit command
    exit_line = "quit"
    cont = await handler.process_line(exit_line)
    # The handler should send goodbye and not continue processing.
    output = b"".join(writer.data)
    assert b"Goodbye!" in output
    assert cont is False

@pytest.mark.asyncio
async def test_process_line_normal(dummy_connection):
    handler, reader, writer = dummy_connection
    writer.data.clear()
    normal_line = "hello world"
    cont = await handler.process_line(normal_line)
    # The handler should call on_command_submitted and then show the prompt.
    output = b"".join(writer.data)
    # Check that the echoed command is present.
    assert f"Echo: {normal_line}".encode('utf-8') in output
    # The prompt should be sent after processing.
    assert b"> " in output
    # The process_line should return True to continue.
    assert cont is True
    # Verify that the command was recorded.
    assert handler.submitted_command == normal_line

def test_process_character_not_implemented(dummy_connection):
    handler, _, _ = dummy_connection
    with pytest.raises(NotImplementedError):
        # process_character should not be used in LineHandler.
        import asyncio
        asyncio.run(handler.process_character("a"))
