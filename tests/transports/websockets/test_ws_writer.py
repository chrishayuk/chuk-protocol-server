#!/usr/bin/env python3
# tests/transports/websocket/test_ws_writer.py

import asyncio
import pytest

from chuk_protocol_server.transports.websocket.ws_writer import WebSocketWriter

# --- Dummy WebSocket Implementation ---
class DummyWebSocket:
    def __init__(self, remote_address=("127.0.0.1", 9999), local_address=("127.0.0.1", 8888)):
        self.remote_address = remote_address
        self.local_address = local_address
        self.sent = []            # Record data sent via send()
        self.closed = False
        self.close_code = None
        self.close_reason = None

    async def send(self, data):
        # Simulate asynchronous sending by appending to the sent list.
        self.sent.append(data)

    async def close(self, code, reason):
        self.closed = True
        self.close_code = code
        self.close_reason = reason

# --- Tests for WebSocketWriter ---

@pytest.fixture
def dummy_websocket():
    return DummyWebSocket()

@pytest.fixture
def writer(dummy_websocket):
    return WebSocketWriter(dummy_websocket)

@pytest.mark.asyncio
async def test_write_and_drain(writer, dummy_websocket):
    """
    Test that calling write() schedules sending data,
    and that drain() waits for those writes to complete.
    """
    # Write some data.
    data1 = b"Test data 1"
    data2 = b"Test data 2"
    await writer.write(data1)
    await writer.write(data2)
    
    # At this point, the writer's _pending_writes should have two tasks.
    assert len(writer._pending_writes) == 2

    # Call drain() to wait for pending writes to complete.
    await writer.drain()

    # After draining, _pending_writes should be cleared.
    assert writer._pending_writes == []
    # And the dummy websocket should have recorded both sends.
    assert dummy_websocket.sent == [data1, data2]

@pytest.mark.asyncio
async def test_drain_error(writer, dummy_websocket, monkeypatch):
    """
    Test that if one of the pending writes fails,
    drain() logs the error and marks the writer as closed.
    """
    # Define a send() that raises an exception.
    async def failing_send(data):
        raise Exception("Send error")
    
    monkeypatch.setattr(dummy_websocket, "send", failing_send)

    # Write some data.
    await writer.write(b"Data that fails")
    with pytest.raises(Exception):
        await writer.drain()
    
    # The writer should be marked as closed.
    assert writer.closed is True
    # The pending writes should have been cleared.
    assert writer._pending_writes == []

@pytest.mark.asyncio
async def test_close_and_wait_closed(writer, dummy_websocket):
    """
    Test that close() marks the writer as closed and wait_closed() calls drain()
    and then closes the underlying websocket.
    """
    # Write some data.
    data = b"Closing test"
    await writer.write(data)
    # Call close() to mark as closed.
    writer.close()
    # wait_closed() should await drain and then call websocket.close.
    await writer.wait_closed()
    
    # The dummy websocket should be marked as closed with a normal closure code (1000).
    assert dummy_websocket.closed is True
    assert dummy_websocket.close_code == 1000
    assert dummy_websocket.close_reason == "Connection closed"

def test_get_extra_info(writer, dummy_websocket):
    """
    Test that get_extra_info() returns the expected extra information.
    """
    # For 'peername', it should return dummy_websocket.remote_address.
    peername = writer.get_extra_info('peername')
    assert peername == dummy_websocket.remote_address
    # For 'sockname', it should return dummy_websocket.local_address.
    sockname = writer.get_extra_info('sockname')
    assert sockname == dummy_websocket.local_address
    # For an unknown key, it should return the default.
    assert writer.get_extra_info('unknown', default="default") == "default"
