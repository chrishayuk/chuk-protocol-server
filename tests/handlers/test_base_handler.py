#!/usr/bin/env python3
# tests/test_base_handler.py

import asyncio
import pytest
from chuk_protocol_server.handlers.base_handler import BaseHandler

# Dummy implementations for the reader and writer
class DummyReader:
    def __init__(self, data: bytes = b''):
        self.data = data
        self.read_called = False

    async def read(self, n: int = -1) -> bytes:
        self.read_called = True
        return self.data

class DummyWriter:
    def __init__(self):
        self.data = []
        self.closed = False
        self.extra_info = {'peername': ('127.0.0.1', 1234)}
        self.write_called = False

    def write(self, data: bytes):
        self.write_called = True
        self.data.append(data)
        # Simulate a case where write is not a coroutine
        return None

    async def drain(self):
        # Simulate drain as an async method that does nothing
        pass

    def get_extra_info(self, name: str, default=None):
        return self.extra_info.get(name, default)

    def close(self):
        self.closed = True

    async def wait_closed(self):
        # Simulate waiting for closure
        self.closed = True

# A dummy subclass of BaseHandler to allow instantiation
class DummyHandler(BaseHandler):
    async def handle_client(self) -> None:
        # Provide a no-op implementation for testing
        pass

    # Provide a dummy send_line method to test end_session with a message.
    async def send_line(self, line: str) -> None:
        await self.send_raw((line + "\r\n").encode('utf-8'))

@pytest.fixture
def dummy_connection():
    reader = DummyReader()
    writer = DummyWriter()
    handler = DummyHandler(reader, writer)
    return handler, reader, writer

@pytest.mark.asyncio
async def test_handle_client_not_implemented():
    # Create an instance of BaseHandler directly to check that NotImplementedError is raised.
    reader = DummyReader()
    writer = DummyWriter()
    handler = BaseHandler(reader, writer)
    with pytest.raises(NotImplementedError):
        await handler.handle_client()

@pytest.mark.asyncio
async def test_send_raw(dummy_connection):
    handler, _, writer = dummy_connection
    data = b"test data"
    await handler.send_raw(data)
    # Check that writer.write was called and data was recorded.
    assert writer.write_called
    assert writer.data[0] == data

@pytest.mark.asyncio
async def test_read_raw_without_timeout(dummy_connection):
    # Prepare reader with data
    data = b"response"
    reader = DummyReader(data)
    writer = DummyWriter()
    handler = DummyHandler(reader, writer)
    result = await handler.read_raw()
    assert result == data
    assert reader.read_called

@pytest.mark.asyncio
async def test_read_raw_with_timeout(dummy_connection):
    # Test that a timeout is raised by using a reader that never returns.
    class HangingReader:
        async def read(self, n: int = -1) -> bytes:
            await asyncio.sleep(2)
            return b""
    reader = HangingReader()
    writer = DummyWriter()
    handler = DummyHandler(reader, writer)
    with pytest.raises(asyncio.TimeoutError):
        await handler.read_raw(timeout=0.1)

@pytest.mark.asyncio
async def test_end_session_with_message(dummy_connection):
    handler, _, writer = dummy_connection
    # Before ending, session_ended should be False and running True.
    assert handler.session_ended is False
    assert handler.running is True

    # Call end_session with a message. DummyHandler provides send_line.
    await handler.end_session("Goodbye")
    # Check that flags have been updated.
    assert handler.session_ended is True
    assert handler.running is False
    # Check that the message was sent (via send_line calling send_raw)
    assert writer.data  # There should be some data written
    # Ensure that the message appears in the sent data (ends with CRLF)
    sent_message = writer.data[0]
    assert sent_message.endswith(b"\r\n")

@pytest.mark.asyncio
async def test_cleanup(dummy_connection):
    handler, _, writer = dummy_connection
    # Call cleanup and verify that writer.close and wait_closed were called.
    await handler.cleanup()
    assert writer.closed

def test_get_extra_info(dummy_connection):
    handler, _, writer = dummy_connection
    # Test that get_extra_info returns the expected value
    peer = handler.get_extra_info('peername')
    assert peer == ('127.0.0.1', 1234)
    # Also test default value behavior
    not_found = handler.get_extra_info('nonexistent', default='default')
    assert not_found == 'default'

@pytest.mark.asyncio
async def test_on_hooks(dummy_connection, caplog):
    handler, _, _ = dummy_connection
    # Call the on_connect hook and check that a debug message is logged.
    await handler.on_connect()
    await handler.on_disconnect()
    # Call on_error and check for an error log entry.
    test_exception = Exception("Test error")
    await handler.on_error(test_exception)
    error_logs = [record.message for record in caplog.records if record.levelname == "ERROR"]
    assert any("Test error" in msg for msg in error_logs)
