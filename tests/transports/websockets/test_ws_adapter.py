#!/usr/bin/env python3
# tests/transports/websockets/test_ws_adapter.py

import asyncio
import pytest
import ssl

from chuk_protocol_server.servers.base_ws_server import BaseWebSocketServer

# --- Dummy Handler for testing ---
class DummyHandler:
    async def handle_client(self):
        pass

# --- Dummy WebSocketReader and WebSocketWriter for patching ---
class DummyWebSocketReader:
    def __init__(self, websocket):
        self.websocket = websocket

class DummyWebSocketWriter:
    def __init__(self, websocket):
        self.websocket = websocket
        self.messages = []
        self._closed = False

    async def write(self, data: bytes):
        self.messages.append(data)

    async def drain(self):
        pass

    def close(self):
        self._closed = True

    async def wait_closed(self):
        self._closed = True

# --- Patch the ws_reader and ws_writer in the module ---
@pytest.fixture(autouse=True)
def patch_ws_io(monkeypatch):
    monkeypatch.setattr(
        "chuk_protocol_server.transports.websocket.ws_reader.WebSocketReader",
        DummyWebSocketReader,
    )
    monkeypatch.setattr(
        "chuk_protocol_server.transports.websocket.ws_writer.WebSocketWriter",
        DummyWebSocketWriter,
    )

# --- Dummy Asyncio Server and Socket that support async context manager ---
class DummySocket:
    def getsockname(self):
        return ("127.0.0.1", 8025)

class DummyWSServer:
    def __init__(self):
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

# --- Dummy Adapter for Testing _force_close_connections ---
class DummyAdapter:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True

# --- Helper subclass to instantiate our BaseWebSocketServer ---
class DummyWebSocketServerSubclass(BaseWebSocketServer):
    async def _connection_handler(self, websocket):
        pass

# --- Tests ---
@pytest.mark.asyncio
async def test_create_server(monkeypatch):
    """
    Test that _create_server calls websockets.serve with expected parameters.
    """
    dummy_ws_instance = DummyWSServer()

    async def dummy_serve(handler, host, port, ssl, ping_interval, ping_timeout, compression, close_timeout):
        # Verify the parameters.
        assert host == "127.0.0.1"
        assert port == 8025
        assert ping_interval == 30
        assert ping_timeout == 10
        assert compression is None
        assert close_timeout == 10
        # Return our dummy server instance.
        return dummy_ws_instance

    monkeypatch.setattr(
        "chuk_protocol_server.servers.base_ws_server.websockets.serve",
        dummy_serve,
    )

    ws_server = DummyWebSocketServerSubclass(
        host="127.0.0.1",
        port=8025,
        handler_class=DummyHandler,
        ping_interval=30,
        ping_timeout=10,
    )
    # Without SSL context.
    ws_server.ssl_context = None
    created_server = await ws_server._create_server()
    assert created_server is dummy_ws_instance

    # With SSL context set.
    ws_server.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    created_server2 = await ws_server._create_server()
    assert created_server2 is dummy_ws_instance

@pytest.mark.asyncio
async def test_start_server(monkeypatch):
    """
    Test that start_server logs the correct address and runs the keep_running loop.
    """
    dummy_ws_instance = DummyWSServer()

    async def dummy_serve(handler, host, port, ssl, ping_interval, ping_timeout, compression, close_timeout):
        return dummy_ws_instance

    monkeypatch.setattr(
        "chuk_protocol_server.servers.base_ws_server.websockets.serve",
        dummy_serve,
    )

    ws_server = DummyWebSocketServerSubclass(
        host="127.0.0.1",
        port=8025,
        handler_class=DummyHandler,
        ping_interval=30,
        ping_timeout=10,
    )
    # Run start_server in background; then set running to False so _keep_running loop exits.
    async def shutdown_after_delay():
        await asyncio.sleep(0.1)
        ws_server.running = False

    shutdown_task = asyncio.create_task(shutdown_after_delay())
    await ws_server.start_server()
    # After start_server returns, verify the dummy server's socket.
    sock_addr = dummy_ws_instance.sockets[0].getsockname()
    assert sock_addr == ("127.0.0.1", 8025)
    await shutdown_task

@pytest.mark.asyncio
async def test_close_server():
    """
    Test that _close_server calls close() and wait_closed() on the server.
    """
    dummy_ws_instance = DummyWSServer()
    ws_server = DummyWebSocketServerSubclass(
        host="127.0.0.1", 
        port=8025, 
        handler_class=DummyHandler
    )
    ws_server.server = dummy_ws_instance
    await ws_server._close_server()
    assert dummy_ws_instance.closed is True

@pytest.mark.asyncio
async def test_force_close_connections():
    """
    Test that _force_close_connections closes all adapters and clears active_connections.
    """
    ws_server = DummyWebSocketServerSubclass(
        host="127.0.0.1", 
        port=8025, 
        handler_class=DummyHandler
    )
    adapter1 = DummyAdapter()
    adapter2 = DummyAdapter()
    ws_server.active_connections = {adapter1, adapter2}
    await ws_server._force_close_connections()
    assert adapter1.closed is True
    assert adapter2.closed is True
    assert len(ws_server.active_connections) == 0

def test_monitoring_enabled(monkeypatch):
    """
    Test that enabling monitoring sets up a session monitor.
    """
    # Create a dummy SessionMonitor.
    class DummySessionMonitor:
        def __init__(self, path):
            self.path = path

    # Monkeypatch SessionMonitor in the module.
    import chuk_protocol_server.servers.base_ws_server as ws_module
    original_SessionMonitor = ws_module.SessionMonitor
    ws_module.SessionMonitor = DummySessionMonitor

    ws_server = DummyWebSocketServerSubclass(
        host="0.0.0.0",
        port=8025,
        handler_class=DummyHandler,
        enable_monitoring=True,
        monitor_path="/monitor-test",
    )
    # __init__ should have set up the session monitor.
    assert ws_server.session_monitor is not None
    assert ws_server.session_monitor.path == "/monitor-test"

    # Restore original SessionMonitor.
    ws_module.SessionMonitor = original_SessionMonitor
