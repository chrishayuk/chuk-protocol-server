#!/usr/bin/env python3
# tests/test_base_server.py

import asyncio
import pytest
from chuk_protocol_server.transports.base_server import BaseServer
from chuk_protocol_server.handlers.base_handler import BaseHandler

# --- Dummy reader and writer for simulating asyncio streams ---

class DummyReader:
    def __init__(self, data: bytes = b""):
        self.data = data
        self.read_called = False
        self.readline_called = False

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

    async def readline(self) -> bytes:
        self.readline_called = True
        # For simplicity, return all data as one line then clear it.
        result = self.data
        self.data = b""
        return result

class DummyWriter:
    def __init__(self):
        self.data = []
        self.extra_info = {'peername': ('127.0.0.1', 4321)}
        self.drain_called = False
        self.closed = False

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

# --- Dummy handler for testing BaseServer ---

class DummyHandlerForServer(BaseHandler):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__(reader, writer)
        self.cleanup_called = False
        self.lines_sent = []

    async def handle_client(self) -> None:
        # Simply wait a short moment to simulate work.
        await asyncio.sleep(0.01)

    async def cleanup(self) -> None:
        self.cleanup_called = True

    async def send_line(self, message: str) -> None:
        # For testing, record the message with CRLF appended.
        if hasattr(self, 'writer'):
            self.writer.write((message + "\r\n").encode('utf-8'))
            await self.writer.drain()
            self.lines_sent.append(message)

# --- Dummy server subclass of BaseServer ---

class DummyServer(BaseServer):
    async def start_server(self) -> None:
        # For testing, just call _create_server and store the result.
        await self._create_server()

    async def _create_server(self) -> object:
        # Return a dummy server object that supports close() and wait_closed().
        class DummyServerInstance:
            def __init__(self):
                self.closed = False
            def close(self):
                self.closed = True
            async def wait_closed(self):
                self.closed = True
        self.server = DummyServerInstance()
        return self.server

# --- Fixtures ---

@pytest.fixture
def dummy_server():
    # Instantiate a DummyServer using DummyHandlerForServer as the handler class.
    server = DummyServer(handler_class=DummyHandlerForServer)
    # Optionally set a welcome message.
    server.welcome_message = "Welcome from Server"
    return server

@pytest.fixture
def dummy_connection():
    # Create dummy reader and writer and a handler instance.
    reader = DummyReader(b"dummy data")
    writer = DummyWriter()
    handler = DummyHandlerForServer(reader, writer)
    return handler, reader, writer

# --- Tests ---

@pytest.mark.asyncio
async def test_create_handler(dummy_server):
    # Test that create_handler returns a handler with server reference and welcome message.
    reader = DummyReader()
    writer = DummyWriter()
    handler = dummy_server.create_handler(reader, writer)
    assert isinstance(handler, DummyHandlerForServer)
    assert handler.server is dummy_server
    # Since dummy_server has welcome_message, if the handler supports it, it should be set.
    # (For this dummy, we assume handler may have an attribute welcome_message.)
    if hasattr(handler, 'welcome_message'):
        assert handler.welcome_message == "Welcome from Server"

@pytest.mark.asyncio
async def test_handle_new_connection(dummy_server):
    # Test that handle_new_connection creates a handler, adds it to active connections,
    # calls handle_client, and then removes it.
    reader = DummyReader()
    writer = DummyWriter()
    # Initially, active_connections should be empty.
    assert dummy_server.get_connection_count() == 0
    await dummy_server.handle_new_connection(reader, writer)
    # After handling, active_connections should be empty again.
    assert dummy_server.get_connection_count() == 0

@pytest.mark.asyncio
async def test_connection_limit(dummy_server):
    # Set max_connections to 1.
    dummy_server.max_connections = 1

    # Create a first connection and add it manually.
    reader1 = DummyReader()
    writer1 = DummyWriter()
    handler1 = dummy_server.create_handler(reader1, writer1)
    dummy_server.active_connections.add(handler1)

    # Now create a second connection; since the limit is reached,
    # the connection should be rejected.
    reader2 = DummyReader()
    writer2 = DummyWriter()
    await dummy_server.handle_new_connection(reader2, writer2)
    # The writer for the rejected connection should have received a rejection message.
    rejection = b"Server is at maximum capacity. Please try again later.\r\n"
    # Since writer2.write is called for rejection, its data should contain the rejection.
    assert any(rejection in chunk for chunk in writer2.data)
    # And writer2 should be closed.
    assert writer2.closed

@pytest.mark.asyncio
async def test_send_global_message(dummy_server):
    # Test that send_global_message sends a message to all active connections.
    # Create two dummy handlers that implement send_line.
    reader1 = DummyReader()
    writer1 = DummyWriter()
    handler1 = dummy_server.create_handler(reader1, writer1)
    reader2 = DummyReader()
    writer2 = DummyWriter()
    handler2 = dummy_server.create_handler(reader2, writer2)
    dummy_server.active_connections.update({handler1, handler2})

    message = "Global message"
    await dummy_server.send_global_message(message)
    # Both handlers should have recorded the message.
    # Since send_line writes the message with CRLF, check that.
    expected = (message + "\r\n").encode('utf-8')
    found1 = any(expected in chunk for chunk in writer1.data)
    found2 = any(expected in chunk for chunk in writer2.data)
    assert found1 and found2

@pytest.mark.asyncio
async def test_shutdown(dummy_server):
    # Test that shutdown stops the server and closes connections.
    # First, create a dummy connection and add it.
    reader = DummyReader()
    writer = DummyWriter()
    handler = dummy_server.create_handler(reader, writer)
    dummy_server.active_connections.add(handler)
    
    # Also, simulate that the server is already created.
    server_instance = await dummy_server._create_server()
    assert server_instance is not None

    # Call shutdown.
    await dummy_server.shutdown()

    # After shutdown, running should be False.
    assert dummy_server.running is False
    # The dummy server instance should be closed.
    assert server_instance.closed is True

@pytest.mark.asyncio
async def test_wait_for_connections_to_close_and_force_close(dummy_server):
    # Test that _wait_for_connections_to_close waits and then forces closure.
    # Create a connection that does not close by itself.
    reader = DummyReader()
    writer = DummyWriter()
    handler = dummy_server.create_handler(reader, writer)
    dummy_server.active_connections.add(handler)

    # Patch handler.writer.wait_closed to never complete.
    original_wait_closed = writer.wait_closed
    async def never_closes():
        await asyncio.sleep(10)
    writer.wait_closed = never_closes

    # Run _wait_for_connections_to_close with a short timeout.
    await dummy_server._wait_for_connections_to_close(timeout=2)
    # After waiting, active_connections should have been forced closed.
    assert dummy_server.get_connection_count() == 0
    # Restore writer.wait_closed for cleanliness.
    writer.wait_closed = original_wait_closed

def test_get_connection_count_and_server_info(dummy_server):
    # Initially, there are no connections.
    assert dummy_server.get_connection_count() == 0
    info = dummy_server.get_server_info()
    assert info['host'] == dummy_server.host
    assert info['port'] == dummy_server.port
    assert info['connections'] == 0
    assert info['running'] is True
    assert info['max_connections'] == dummy_server.max_connections
    assert info['connection_timeout'] == dummy_server.connection_timeout
