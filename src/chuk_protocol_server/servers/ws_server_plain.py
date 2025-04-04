#!/usr/bin/env python3
# chuk_protocol_server/servers/ws_server_plain.py
"""
Plain WebSocket Server with Session Monitoring

Accepts WebSocket connections as plain text, skipping Telnet negotiation.
Supports monitoring sessions through a separate WebSocket endpoint.
"""
import asyncio
import logging
import uuid
from typing import Type, Optional, List

# websockets
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_ws_server import BaseWebSocketServer
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter

# logger
logger = logging.getLogger('chuk-protocol-server')

class PlainWebSocketServer(BaseWebSocketServer):
    """
    Plain WebSocket server that processes incoming messages as plain text
    (no Telnet negotiation), with optional TLS if ssl_cert and ssl_key are given.
    Supports monitoring sessions through a separate endpoint if enabled.
    """
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8025,
        handler_class: Type[BaseHandler] = None,
        path: str = '/ws',
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: Optional[List[str]] = None,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
        enable_monitoring: bool = False,
        monitor_path: str = '/monitor',
    ):
        super().__init__(
            host=host,
            port=port,
            handler_class=handler_class,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            allow_origins=allow_origins,
            ssl_cert=ssl_cert,
            ssl_key=ssl_key,
            enable_monitoring=enable_monitoring,
            monitor_path=monitor_path
        )
        self.path = path
        self.transport = "websocket"

    async def _connection_handler(self, websocket: WebSocketServerProtocol):
        """
        Handle a WebSocket connection in plain text mode.
        """
        # Check if this is a monitoring connection
        if self.enable_monitoring and self.session_monitor:
            try:
                request_path = websocket.request.path
                if self.session_monitor.is_monitor_path(request_path):
                    logger.info(f"Monitoring viewer connected: {websocket.remote_address}")
                    await self.session_monitor.handle_viewer_connection(websocket)
                    return
            except AttributeError:
                logger.error("Cannot access websocket.request.path")
        
        # Reject connection if we're at max connections
        if self.max_connections and len(self.active_connections) >= self.max_connections:
            logger.warning(f"Maximum connections ({self.max_connections}) reached, rejecting WebSocket connection")
            await websocket.close(code=1008, reason="Server at capacity")
            return
            
        # Validate request path
        try:
            raw_path = websocket.request.path
        except AttributeError:
            logger.error("Plain WS: websocket.request.path not available")
            await websocket.close(code=1011, reason="Internal server error")
            return

        expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
        logger.debug(f"Plain WS: path='{raw_path}', expected='{expected_path}'")
        if raw_path != expected_path:
            logger.warning(f"Plain WS: Rejected connection: invalid path '{raw_path}'")
            await websocket.close(code=1003, reason=f"Invalid path {raw_path}")
            return

        # Optional CORS check
        try:
            headers = getattr(websocket, 'request_headers', {})
            origin = headers.get('Origin') or headers.get('origin') or headers.get('HTTP_ORIGIN', '')
            if origin and self.allow_origins and ('*' not in self.allow_origins) and (origin not in self.allow_origins):
                logger.warning(f"Plain WS: Origin '{origin}' not allowed")
                await websocket.close(code=403, reason="Origin not allowed")
                return
        except Exception as err:
            logger.error(f"Plain WS: CORS error: {err}")
            await websocket.close(code=1011, reason="CORS error")
            return

        # Create appropriate adapter (monitorable if monitoring is enabled)
        if self.enable_monitoring and self.session_monitor:
            # Import the interceptor here to avoid circular imports
            from chuk_protocol_server.transports.websocket.ws_interceptor import WebSocketInterceptor
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Create interceptor for protocol-level monitoring
            interceptor = WebSocketInterceptor(
                websocket=websocket,
                session_id=session_id,
                monitor=self.session_monitor
            )
            
            # Create the adapter with the interceptor
            adapter = MonitorableWebSocketAdapter(interceptor, self.handler_class)
            adapter.session_id = session_id  # Use the same session ID
            adapter.monitor = self.session_monitor
            adapter.is_monitored = True
            
            logger.debug(f"Created monitorable adapter with session ID: {adapter.session_id}")
        else:
            adapter = WebSocketAdapter(websocket, self.handler_class)
            
        adapter.server = self
        adapter.mode = "simple"
        
        # Pass welcome message if configured
        if self.welcome_message:
            adapter.welcome_message = self.welcome_message
            
        self.active_connections.add(adapter)
        try:
            # If connection_timeout is set, create a timeout wrapper
            if self.connection_timeout:
                try:
                    await asyncio.wait_for(adapter.handle_client(), timeout=self.connection_timeout)
                except asyncio.TimeoutError:
                    logger.info(f"Connection timeout ({self.connection_timeout}s) for {adapter.addr}")
            else:
                await adapter.handle_client()
            
            # Check if the session was ended by the handler (e.g., quit command)
            if hasattr(adapter.handler, 'session_ended') and adapter.handler.session_ended:
                # The session was explicitly ended by the handler
                logger.debug(f"Plain WS: Session ended for {adapter.addr}")
                # Ensure the WebSocket is properly closed
                if not getattr(websocket, 'closed', False):
                    await websocket.close(1000, "Session ended")
                
        except ConnectionClosed as e:
            logger.info(f"Plain WS: Connection closed: {e}")
        except Exception as e:
            logger.error(f"Plain WS: Error handling client: {e}")
        finally:
            self.active_connections.discard(adapter)