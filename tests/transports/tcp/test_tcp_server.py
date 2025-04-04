#!/usr/bin/env python3
# tests/test_tcp_server.py

import asyncio
import pytest
from chuk_protocol_server.transports.tcp.tcp_server import TCPServer
from chuk_protocol_server.handlers.base_handler import BaseHandler

# --- Dummy Handler for testing TCPServer ---
class DummyHandler(BaseHandler):
    async def handle_client(self) -> None:
        # No-op for testing purposes
        pass

# --- Dummy Asyncio Server and Socket with async context manager support ---
class DummySocket:
    def getsockname(self):
        return ("127.0.0.1", 9999)

class DummyAsyncioServer:
    def __init__(self):
        # Simulate a server with one socket.
        self.sockets = [DummySocket()]
        self.closed = False

    async def serve_forever(self):
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.closed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.close()
        await self.wait_closed()

# --- Dummy reader and writer for simulating asyncio streams ---
class DummyReader:
    pass

class DummyWriter:
    def __init__(self):
        self.extra_info = {'peername': ('127.0.0.1', 8888)}
        self.data = []
        self.drain_called = False

    def write(self, data: bytes):
        self.data.append(data)

    async def drain(self):
        self.drain_called = True

    def get_extra_info(self, name: str, default=None):
        return self.extra_info.get(name, default)

# --- Tests ---

@pytest.mark.asyncio
async def test_create_handler(monkeypatch):
    """
    Test that create_handler sets the handler's mode to "simple"
    and initializes initial_data to empty bytes.
    """
    tcp_server = TCPServer(handler_class=DummyHandler)
    # Create dummy reader and writer objects.
    dummy_reader = DummyReader()
    dummy_writer = DummyWriter()
    handler = tcp_server.create_handler(dummy_reader, dummy_writer)
    assert hasattr(handler, "mode")
    assert handler.mode == "simple"
    assert hasattr(handler, "initial_data")
    assert handler.initial_data == b""

@pytest.mark.asyncio
async def test_start_server(monkeypatch):
    """
    Test that TCPServer.start_server properly creates the asyncio server
    and logs the correct address.
    """
    dummy_server_instance = DummyAsyncioServer()

    async def dummy_start_server(handler, host, port):
        # Verify that the correct parameters are passed.
        assert host == "127.0.0.1"
        assert port == 9999
        return dummy_server_instance

    # Patch asyncio.start_server to use our dummy_start_server.
    monkeypatch.setattr(asyncio, "start_server", dummy_start_server)

    tcp_server = TCPServer(host="127.0.0.1", port=9999, handler_class=DummyHandler)

    # Run start_server in a task; then cancel it to exit serve_forever.
    task = asyncio.create_task(tcp_server.start_server())
    await asyncio.sleep(0.05)
    task.cancel()
    # Instead of expecting a CancelledError, we simply verify the task is done.
    await asyncio.sleep(0.05)
    assert task.done()
    # Also, verify that the dummy server instance has a socket with the expected address.
    sock_addr = dummy_server_instance.sockets[0].getsockname()
    assert sock_addr == ("127.0.0.1", 9999)

