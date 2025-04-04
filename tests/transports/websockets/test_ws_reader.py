#!/usr/bin/env python3
# tests/transports/websocket/test_ws_reader.py

import asyncio
import pytest
from websockets.exceptions import ConnectionClosed

from chuk_protocol_server.transports.websocket.ws_reader import WebSocketReader

# --- Dummy WebSocket Implementation ---
class DummyWebSocket:
    def __init__(self, messages):
        # messages is a list of messages to return from recv()
        self.messages = messages.copy()
        self.remote_address = ("127.0.0.1", 1234)
    
    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        # Simulate end-of-connection by raising ConnectionClosed with a valid parameter.
        raise ConnectionClosed(1000, "dummy close", False)

# --- Test Cases ---

@pytest.mark.asyncio
async def test_read_text_message():
    """
    Test that a text message is read and returned as bytes.
    """
    # Create a dummy websocket that will return a text message.
    dummy_ws = DummyWebSocket(["Hello"])
    reader = WebSocketReader(dummy_ws)
    # Call read() with n=-1 to read all available data.
    data = await reader.read(-1)
    # The text "Hello" should be encoded to UTF-8.
    assert data == b"Hello"

@pytest.mark.asyncio
async def test_read_binary_message():
    """
    Test that a binary message is read without modification.
    """
    dummy_ws = DummyWebSocket([b"World"])
    reader = WebSocketReader(dummy_ws)
    data = await reader.read(-1)
    assert data == b"World"

@pytest.mark.asyncio
async def test_read_buffering():
    """
    Test that read() with a byte limit returns part of the data and buffers the rest.
    """
    # Use a text message; "Hello" encoded is b"Hello"
    dummy_ws = DummyWebSocket(["Hello"])
    reader = WebSocketReader(dummy_ws)
    # First read only 3 bytes.
    part1 = await reader.read(3)
    assert part1 == b"Hel"
    # Second read returns the rest.
    part2 = await reader.read(-1)
    assert part2 == b"lo"

@pytest.mark.asyncio
async def test_read_connection_closed():
    """
    Test that when ConnectionClosed is raised, read() returns the buffered data.
    """
    # Create a dummy websocket that returns a message then raises ConnectionClosed.
    dummy_ws = DummyWebSocket(["Partial"])
    reader = WebSocketReader(dummy_ws)
    # Read the message.
    data1 = await reader.read(-1)
    assert data1 == b"Partial"
    # Now, since no more messages, a call to read() should trigger ConnectionClosed
    # and return empty bytes.
    data2 = await reader.read(-1)
    assert data2 == b""
    # at_eof() should now return True.
    assert reader.at_eof() is True

@pytest.mark.asyncio
async def test_readline_single_message():
    """
    Test that readline() returns a complete line when the newline is in a single message.
    """
    # Message contains a newline.
    dummy_ws = DummyWebSocket(["Line one\nExtra data"])
    reader = WebSocketReader(dummy_ws)
    line = await reader.readline()
    # The line should include the newline character.
    assert line == b"Line one\n"
    # A subsequent read should return the rest.
    remaining = await reader.read(-1)
    assert remaining == b"Extra data"

@pytest.mark.asyncio
async def test_readline_split_messages():
    """
    Test that readline() properly handles newlines split across messages.
    """
    # First message does not contain a newline; second does.
    dummy_ws = DummyWebSocket(["Partial ", "line\nRest"])
    reader = WebSocketReader(dummy_ws)
    line = await reader.readline()
    # Expect the concatenation of "Partial " and "line\n" to be returned.
    assert line == b"Partial line\n"
    remaining = await reader.read(-1)
    assert remaining == b"Rest"

@pytest.mark.asyncio
async def test_at_eof():
    """
    Test that at_eof() returns True when the connection is closed and buffer is empty.
    """
    dummy_ws = DummyWebSocket(["Data"])
    reader = WebSocketReader(dummy_ws)
    data = await reader.read(-1)
    assert data == b"Data"
    # Now, further reads should raise ConnectionClosed and result in empty bytes.
    data2 = await reader.read(-1)
    assert data2 == b""
    assert reader.at_eof() is True
