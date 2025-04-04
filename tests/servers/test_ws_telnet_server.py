import asyncio
import pytest
import uuid

from websockets.exceptions import ConnectionClosed
from chuk_protocol_server.servers.ws_telnet_server import WSTelnetServer
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter

# --- Dummy WebSocket and Request objects --- #
class DummyRequest:
    def __init__(self, path):
        self.path = path

class DummyWebSocket:
    def __init__(self, path, request_headers=None, remote_address=("127.0.0.1", 12345)):
        self.request = DummyRequest(path)
        self.request_headers = request_headers or {}
        self.remote_address = remote_address
        self.closed = False
        self.close_called = False
        self.close_code = None
        self.close_reason = None

    async def close(self, code=1000, reason=""):
        self.closed = True
        self.close_called = True
        self.close_code = code
        self.close_reason = reason

# --- Dummy Session Monitor for testing monitoring connections --- #
class DummySessionMonitor:
    def __init__(self, monitor_path="/monitor"):
        self.monitor_path = monitor_path
        self.viewer_connections = []
    
    def is_monitor_path(self, path):
        return path == self.monitor_path
    
    async def handle_viewer_connection(self, websocket):
        self.viewer_connections.append(websocket)
        # Simulate immediate closure for testing.
        await websocket.close(1000, "Monitoring closed")

# --- Dummy Adapter that simply completes immediately --- #
class DummyAdapter:
    def __init__(self, websocket, handler_class):
        self.websocket = websocket
        self.handler_class = handler_class
        self.server = None
        self.mode = None
        self.welcome_message = None
        self.session_id = None
        self.monitor = None
        self.is_monitored = False
        self.addr = websocket.remote_address

    async def handle_client(self):
        # Immediately return to simulate a finished connection.
        pass

# --- Dummy Handler class (can be empty for testing) --- #
class DummyHandler:
    pass

# --- Fixture to create a configured WSTelnetServer instance --- #
@pytest.fixture
def ws_telnet_server(monkeypatch):
    server = WSTelnetServer(
        host="127.0.0.1",
        port=8026,
        handler_class=DummyHandler,
        path="/ws_telnet",
        allow_origins=["http://allowed.com"],
        enable_monitoring=True,
        monitor_path="/monitor"
    )
    # Ensure active_connections is a set.
    server.active_connections = set()
    # For testing, set max_connections to None unless overridden.
    server.max_connections = None

    # Patch the adapters to use DummyAdapter instead of the real ones.
    monkeypatch.setattr(
        "chuk_protocol_server.servers.ws_telnet_server.WebSocketAdapter",
        DummyAdapter
    )
    monkeypatch.setattr(
        "chuk_protocol_server.servers.ws_telnet_server.MonitorableWebSocketAdapter",
        DummyAdapter
    )
    return server

@pytest.mark.asyncio
async def test_valid_connection(ws_telnet_server):
    """
    Test a valid WebSocket Telnet connection:
      - Correct path ("/ws_telnet")
      - Allowed origin
    Expect that the adapter is created, mode is set to "telnet", and the connection is handled normally.
    """
    dummy_ws = DummyWebSocket(path="/ws_telnet", request_headers={"Origin": "http://allowed.com"})
    ws_telnet_server.active_connections.clear()
    
    await ws_telnet_server._connection_handler(dummy_ws)
    # For a valid connection, the adapter is created and then removed after handle_client.
    # The WebSocket is not closed.
    assert dummy_ws.closed is False
    assert len(ws_telnet_server.active_connections) == 0

@pytest.mark.asyncio
async def test_invalid_path(ws_telnet_server):
    """
    Test that a WebSocket connection with an invalid path is rejected.
    Expect the connection to be closed with code 1003.
    """
    dummy_ws = DummyWebSocket(path="/wrong_path", request_headers={"Origin": "http://allowed.com"})
    await ws_telnet_server._connection_handler(dummy_ws)
    assert dummy_ws.closed is True
    assert dummy_ws.close_code == 1003
    assert "Endpoint" in dummy_ws.close_reason

@pytest.mark.asyncio
async def test_cors_rejection(ws_telnet_server):
    """
    Test that a WebSocket connection with a disallowed origin is rejected.
    Expect the connection to be closed with code 403.
    """
    dummy_ws = DummyWebSocket(path="/ws_telnet", request_headers={"Origin": "http://notallowed.com"})
    await ws_telnet_server._connection_handler(dummy_ws)
    assert dummy_ws.closed is True
    assert dummy_ws.close_code == 403

@pytest.mark.asyncio
async def test_monitor_connection(ws_telnet_server):
    """
    Test that a connection to the monitoring endpoint is handled by the session monitor.
    Expect the DummySessionMonitor to record the viewer connection and close the WebSocket.
    """
    dummy_monitor = DummySessionMonitor(monitor_path="/monitor")
    ws_telnet_server.session_monitor = dummy_monitor
    # Create a WebSocket whose request path matches the monitor path.
    dummy_ws = DummyWebSocket(path="/monitor", request_headers={"Origin": "http://allowed.com"})
    await ws_telnet_server._connection_handler(dummy_ws)
    # The monitor should have recorded one viewer connection.
    assert len(dummy_monitor.viewer_connections) == 1
    # And the WebSocket should be closed.
    assert dummy_ws.closed is True

@pytest.mark.asyncio
async def test_max_connections(ws_telnet_server):
    """
    Test that when the maximum connections limit is reached, a new connection is rejected.
    Expect the connection to be closed with code 1008.
    """
    # Set max_connections to 1 and simulate one active connection.
    ws_telnet_server.max_connections = 1
    ws_telnet_server.active_connections.clear()
    ws_telnet_server.active_connections.add("dummy_connection")
    
    dummy_ws = DummyWebSocket(path="/ws_telnet", request_headers={"Origin": "http://allowed.com"})
    await ws_telnet_server._connection_handler(dummy_ws)
    assert dummy_ws.closed is True
    assert dummy_ws.close_code == 1008

@pytest.mark.asyncio
async def test_missing_request_path(ws_telnet_server):
    """
    Test that if the WebSocket does not have a request.path attribute, the connection is rejected.
    Expect the connection to be closed with code 1011.
    """
    # Define a WebSocket that lacks a proper request.
    class NoPathWebSocket(DummyWebSocket):
        def __init__(self, request_headers=None):
            self.request = None  # Simulate missing request attribute.
            self.request_headers = request_headers or {}
            self.remote_address = ("127.0.0.1", 12345)
            self.closed = False
            self.close_called = False
            self.close_code = None
            self.close_reason = None
        async def close(self, code=1000, reason=""):
            self.closed = True
            self.close_called = True
            self.close_code = code
            self.close_reason = reason

    dummy_ws = NoPathWebSocket(request_headers={"Origin": "http://allowed.com"})
    await ws_telnet_server._connection_handler(dummy_ws)
    assert dummy_ws.closed is True
    assert dummy_ws.close_code == 1011
