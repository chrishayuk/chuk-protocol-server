#!/usr/bin/env python3
# tests/test_connection_handler.py

import asyncio
import pytest
from chuk_protocol_server.handlers.connection_handler import ConnectionHandler

# Dummy reader simulating an asyncio.StreamReader
class DummyReader:
    def __init__(self, data: bytes = b''):
        self.data = data
        self.read_called = False

    async def read(self, n: int = -1) -> bytes:
        self.read_called = True
        if n == -1:
            result = self.data
            self.data = b""
            return result
        else:
            result = self.data[:n]
            self.data = self.data[n:]
            return result

# Dummy writer simulating an asyncio.StreamWriter
class DummyWriter:
    def __init__(self):
        self.data = []
        self.closed = False
        self.extra_info = {'peername': ('127.0.0.1', 5678)}
        self.drain_called = False

    def write(self, data: bytes):
        self.data.append(data)

    async def drain(self):
        self.drain_called = True

    def get_extra_info(self, name: str, default=None):
        return self.extra_info.get(name, default)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.closed = True

# Create a dummy subclass to instantiate ConnectionHandler for testing purposes.
class DummyConnectionHandler(ConnectionHandler):
    async def handle_client(self) -> None:
        # Dummy implementation: do nothing.
        pass

@pytest.fixture
def dummy_connection():
    reader = DummyReader(b"test data")
    writer = DummyWriter()
    handler = DummyConnectionHandler(reader, writer)
    return handler, reader, writer

@pytest.mark.asyncio
async def test_handle_client_not_implemented():
    # Test that the base class method (if not overridden) raises NotImplementedError.
    # Here we instantiate ConnectionHandler directly.
    reader = DummyReader()
    writer = DummyWriter()
    handler = ConnectionHandler(reader, writer)
    with pytest.raises(NotImplementedError):
        await handler.handle_client()

@pytest.mark.asyncio
async def test_read_raw_without_timeout(dummy_connection):
    handler, reader, _ = dummy_connection
    # Ensure that read_raw returns the expected data.
    result = await handler.read_raw()
    assert result == b"test data"
    assert reader.read_called

@pytest.mark.asyncio
async def test_read_raw_with_timeout():
    # Create a reader that never returns to simulate a timeout.
    class HangingReader:
        async def read(self, n: int = -1) -> bytes:
            await asyncio.sleep(2)
            return b""
    reader = HangingReader()
    writer = DummyWriter()
    handler = DummyConnectionHandler(reader, writer)
    with pytest.raises(asyncio.TimeoutError):
        await handler.read_raw(timeout=0.1)

@pytest.mark.asyncio
async def test_write_raw(dummy_connection):
    handler, _, writer = dummy_connection
    data = b"hello world"
    await handler.write_raw(data)
    # Check that data was written and drain was called.
    assert writer.data[0] == data
    assert writer.drain_called

def test_get_extra_info(dummy_connection):
    handler, _, writer = dummy_connection
    # Test that get_extra_info returns the expected value.
    peer = handler.get_extra_info('peername')
    assert peer == ('127.0.0.1', 5678)
    # Test with a key that doesn't exist.
    default_value = handler.get_extra_info('nonexistent', default='default')
    assert default_value == 'default'
