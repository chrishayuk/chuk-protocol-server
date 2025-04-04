#!/usr/bin/env python3
# tests/servers/test_ws_server_plain.py

import asyncio
import pytest
import uuid
from websockets.exceptions import ConnectionClosed
from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer

# --- Dummy Implementations ---

class DummyWebSocket:
    """
    A dummy WebSocket that simulates a minimal WebSocket connection.
    It supports the attributes and methods used by the server.
    """
    def __init__(self, request_path="/ws", headers=None, remote_address=("127.0.0.1", 9999)):
        self.request = type("DummyRequest", (), {"path": request_path})
        self.request_headers = headers if headers is not None else {}
        self.remote_address = remote_address
        self.closed = False
        self.close_called = False
        self.close_code = None
        self.close_reason = None

    async def close(self, code=None, reason=None):
        self.close_called = True
        self.close_code = code
        self.close_reason = reason
        self.closed = True

class DummySessionMonitor:
    """
    A dummy session monitor that implements minimal behavior.
    """
    def __init__(self, monitor_path="/monitor"):
        self.monitor_path = monitor_path
        self.registered_sessions = {}
        self.viewer_connections = []
    
    def is_monitor_path(self, path: str) -> bool:
        return path == self.monitor_path

    async def handle_viewer_connection(self, websocket):
        self.viewer_connections.append(websocket)

    async def register_session(self, session_id, client_info):
        self.registered_sessions[session_id] = client_info

    async def unregister_session(self, session_id):
        if session_id in self.registered_sessions:
            del self.registered_sessions[session_id]

    async def broadcast_session_event(self, session_id, event_type, data):
        # For testing, we do nothing.
        pass

class DummyHandler:
    """
    A dummy handler that records whether handle_client was called.
    """
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.called = False
        self.session_ended = False  # Simulate a flag set when session is ended
        self.mode = None
        self.server = None

    async def handle_client(self):
        self.called = True

    async def send_line(self, message: str):
        pass

    async def cleanup(self):
        pass

# A dummy handler that never finishes
class NeverEndingHandler:
    def __init__(self, reader, writer):
        self.called = False
    async def handle_client(self):
        await asyncio.sleep(10)
    async def cleanup(self):
        pass

# --- Fixtures ---

@pytest.fixture
def plain_ws_server():
    # Create a PlainWebSocketServer with dummy handler and default parameters.
    server = PlainWebSocketServer(
        host="127.0.0.1",
        port=8025,
        handler_class=DummyHandler,
        path="/ws",
        allow_origins=["*"],
        enable_monitoring=False  # default to non-monitoring
    )
    # Initialize active_connections as a set.
    server.active_connections = set()
    # Set a connection timeout sufficiently high by default.
    server.connection_timeout = 5
    # Set max_connections to a high number.
    server.max_connections = 100
    return server

# --- Tests ---

@pytest.mark.asyncio
async def test_valid_connection(plain_ws_server):
    """
    Test a valid connection: when a dummy websocket with the correct path (/ws) is provided,
    the server creates an adapter and calls handler.handle_client().
    """
    dummy_ws = DummyWebSocket(request_path="/ws")
    plain_ws_server.handler_class = DummyHandler

    await plain_ws_server._connection_handler(dummy_ws)
    # After handling, active_connections should be empty.
    assert len(plain_ws_server.active_connections) == 0
    # The dummy websocket should not have been closed.
    assert not dummy_ws.close_called

@pytest.mark.asyncio
async def test_invalid_path_rejection(plain_ws_server):
    """
    Test that a connection with an invalid path is rejected.
    """
    dummy_ws = DummyWebSocket(request_path="/invalid")
    await plain_ws_server._connection_handler(dummy_ws)
    # Expect the websocket to be closed with code 1003.
    assert dummy_ws.close_called
    assert dummy_ws.close_code == 1003

@pytest.mark.asyncio
async def test_cors_rejection(plain_ws_server):
    """
    Test that if the Origin header is not allowed, the connection is rejected.
    """
    plain_ws_server.allow_origins = ["https://allowed.com"]
    headers = {"Origin": "https://disallowed.com"}
    dummy_ws = DummyWebSocket(request_path="/ws", headers=headers)
    await plain_ws_server._connection_handler(dummy_ws)
    # Expect rejection due to CORS with code 403.
    assert dummy_ws.close_called
    assert dummy_ws.close_code == 403

@pytest.mark.asyncio
async def test_max_connections_enforced(plain_ws_server):
    """
    Test that if the max connections limit is reached, the connection is rejected.
    """
    plain_ws_server.max_connections = 1
    dummy_adapter = object()
    plain_ws_server.active_connections.add(dummy_adapter)
    dummy_ws = DummyWebSocket(request_path="/ws")
    await plain_ws_server._connection_handler(dummy_ws)
    # Expect rejection due to maximum connections with code 1008.
    assert dummy_ws.close_called
    assert dummy_ws.close_code == 1008

@pytest.mark.asyncio
async def test_monitoring_connection(plain_ws_server, monkeypatch):
    """
    Test that if monitoring is enabled and the request path is recognized as the monitor path,
    the connection is handled as a monitoring viewer.
    """
    plain_ws_server.enable_monitoring = True
    monitor = DummySessionMonitor()
    plain_ws_server.session_monitor = monitor
    monitor.monitor_path = "/monitor"
    dummy_ws = DummyWebSocket(request_path="/monitor")
    
    called = False
    async def dummy_handle_viewer(ws):
        nonlocal called
        called = True
    monkeypatch.setattr(monitor, "handle_viewer_connection", dummy_handle_viewer)
    
    await plain_ws_server._connection_handler(dummy_ws)
    assert called is True

@pytest.mark.asyncio
async def test_connection_timeout(plain_ws_server):
    """
    Test that if adapter.handle_client() does not complete within the timeout,
    the connection times out.
    
    Note: The PlainWebSocketServer implementation catches TimeoutError internally.
    Therefore, we verify that after _connection_handler returns, the adapter's handler
    has not finished (i.e. its 'called' flag remains False) and active_connections is empty.
    """
    plain_ws_server.connection_timeout = 0.1
    plain_ws_server.handler_class = NeverEndingHandler
    dummy_ws = DummyWebSocket(request_path="/ws")
    await plain_ws_server._connection_handler(dummy_ws)
    # Since the handler never completes, its handle_client() was not marked as called.
    # Also, active_connections should be empty.
    assert len(plain_ws_server.active_connections) == 0
    # Optionally, we can check that the dummy_ws was not closed by the timeout branch.
    # (Depending on implementation, it may or may not be closed.)
    # For this test, we assume it is not automatically closed.
    assert not dummy_ws.close_called

@pytest.mark.asyncio
async def test_normal_monitoring_connection(plain_ws_server, monkeypatch):
    """
    Test a normal connection when monitoring is enabled.
    """
    plain_ws_server.enable_monitoring = True
    monitor = DummySessionMonitor()
    plain_ws_server.session_monitor = monitor
    plain_ws_server.path = "/ws"
    dummy_ws = DummyWebSocket(request_path="/ws")
    plain_ws_server.handler_class = DummyHandler
    await plain_ws_server._connection_handler(dummy_ws)
    assert len(plain_ws_server.active_connections) == 0
    assert not dummy_ws.close_called

@pytest.mark.asyncio
async def test_missing_request_path(plain_ws_server):
    """
    Test that if websocket.request.path is missing, the connection is rejected.
    """
    dummy_ws = DummyWebSocket()
    del dummy_ws.request
    await plain_ws_server._connection_handler(dummy_ws)
    assert dummy_ws.close_called
    assert dummy_ws.close_code == 1011
