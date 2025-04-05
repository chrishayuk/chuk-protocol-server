import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from websockets.server import WebSocketServerProtocol
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.handlers.base_handler import BaseHandler

# Dummy handler to check that the adapter passes the websocket.
class DummyHandler(BaseHandler):
    def __init__(self, reader, writer):
        super().__init__(reader, writer)
        self.websocket_received = None
        self.called = False

    async def handle_client(self):
        self.called = True
        # Record the websocket passed in
        self.websocket_received = getattr(self, 'websocket', None)

@pytest.fixture
def dummy_websocket():
    # Create a dummy websocket with request attributes.
    ws = MagicMock(spec=WebSocketServerProtocol)
    ws.request = MagicMock()
    ws.request.path = "/ws?foo=bar"
    ws.remote_address = ("127.0.0.1", 12345)
    ws.request_headers = {"Origin": "http://example.com"}
    ws.close = AsyncMock()
    return ws

@pytest.fixture
def dummy_adapter(dummy_websocket):
    # Create the adapter with a dummy handler.
    return WebSocketAdapter(dummy_websocket, DummyHandler)

@pytest.mark.asyncio
async def test_adapter_passes_websocket(dummy_adapter, dummy_websocket):
    # Run the adapter's handle_client.
    await dummy_adapter.handle_client()
    # Check that the handler received the websocket.
    assert dummy_adapter.handler.called
    assert dummy_adapter.handler.websocket == dummy_websocket

@pytest.mark.asyncio
async def test_path_extraction_and_validation():
    # Test that a dummy websocket with a valid path is accepted.
    from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer
    # Create a dummy websocket that simulates a valid connection.
    ws = MagicMock(spec=WebSocketServerProtocol)
    ws.request = MagicMock()
    ws.request.path = "/ws?foo=bar"
    ws.remote_address = ("127.0.0.1", 54321)
    ws.request_headers = {"Origin": "http://example.com"}
    ws.close = AsyncMock()
    
    server = PlainWebSocketServer(
        host="127.0.0.1",
        port=8025,
        handler_class=DummyHandler,
        path="/ws"
    )
    server.active_connections = set()
    server.max_connections = 10
    server.connection_timeout = 2
    
    await server._connection_handler(ws)
    ws.close.assert_not_awaited()
    # Check that the websocket has _original_path and full_path set.
    assert hasattr(ws, "_original_path")
    assert ws._original_path == "/ws?foo=bar"
    assert hasattr(ws, "full_path")
    assert ws.full_path == "/ws?foo=bar"

@pytest.mark.asyncio
async def test_invalid_path_rejection():
    # Test that an invalid path results in connection closure.
    from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer
    ws = MagicMock(spec=WebSocketServerProtocol)
    ws.request = MagicMock()
    ws.request.path = "/invalid?foo=bar"
    ws.remote_address = ("127.0.0.1", 55555)
    ws.request_headers = {"Origin": "http://example.com"}
    ws.close = AsyncMock()
    
    server = PlainWebSocketServer(
        host="127.0.0.1",
        port=8025,
        handler_class=DummyHandler,
        path="/ws"
    )
    server.active_connections = set()
    server.max_connections = 10
    server.connection_timeout = 2

    await server._connection_handler(ws)
    ws.close.assert_awaited_once()
    close_args = ws.close.await_args[1]
    assert close_args.get("code") == 1003
    # The error message should include "Invalid path"
    assert "Invalid path" in close_args.get("reason", "")
