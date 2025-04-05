#!/usr/bin/env python3
# chuk_protocol_server/servers/ws_server_plain.py
"""
Plain WebSocket Server with Session Monitoring

Accepts WebSocket connections as plain text, skipping Telnet negotiation.
Supports monitoring sessions through a separate endpoint.
"""
import asyncio
import logging
import uuid
from typing import Type, Optional, List
from urllib.parse import urlparse

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_ws_server import BaseWebSocketServer
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter

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
        path: Optional[str] = '/ws',  # can be None to accept any path
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
            
        # Capture the original path immediately.
        try:
            raw_path = websocket.request.path
            setattr(websocket, '_original_path', raw_path)
            logger.debug(f"Captured original path: {raw_path}")
        except AttributeError:
            logger.error("Plain WS: websocket.request.path not available")
            await websocket.close(code=1011, reason="Internal server error")
            return

        # If a fixed path is configured, validate it.
        if self.path is not None:
            parsed_path = urlparse(raw_path)
            actual_path = parsed_path.path or "/"
            expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
            logger.debug(f"Plain WS: raw_path='{raw_path}', actual_path='{actual_path}', expected prefix='{expected_path}'")
            if not actual_path.startswith(expected_path):
                logger.warning(f"Plain WS: Rejected connection: path '{raw_path}' does not start with expected prefix '{expected_path}'")
                # Updated error message to match test expectation.
                await websocket.close(code=1003, reason=f"Invalid path {raw_path}")
                return
            # Save the full path for later use by the handler.
            websocket.full_path = raw_path
        else:
            logger.debug("Plain WS: path is None => accepting any path")

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

        # Create adapter (monitorable if monitoring is enabled)
        if self.enable_monitoring and self.session_monitor:
            from chuk_protocol_server.transports.websocket.ws_interceptor import WebSocketInterceptor
            
            session_id = str(uuid.uuid4())
            interceptor = WebSocketInterceptor(
                websocket=websocket,
                session_id=session_id,
                monitor=self.session_monitor
            )
            adapter = MonitorableWebSocketAdapter(interceptor, self.handler_class)
            adapter.session_id = session_id
            adapter.monitor = self.session_monitor
            adapter.is_monitored = True
            
            logger.debug(f"Created monitorable adapter with session ID: {adapter.session_id}")
        else:
            adapter = WebSocketAdapter(websocket, self.handler_class)
            
        adapter.server = self
        adapter.mode = "simple"  # no Telnet negotiation in plain mode
        
        # Pass welcome message if configured
        if self.welcome_message:
            adapter.welcome_message = self.welcome_message
            
        self.active_connections.add(adapter)
        try:
            # If connection_timeout is set, use asyncio.wait_for
            if self.connection_timeout:
                try:
                    await asyncio.wait_for(adapter.handle_client(), timeout=self.connection_timeout)
                except asyncio.TimeoutError:
                    logger.info(f"Connection timeout ({self.connection_timeout}s) for {adapter.addr}")
            else:
                await adapter.handle_client()
            
            # Check if session was ended by the handler
            if hasattr(adapter.handler, 'session_ended') and adapter.handler.session_ended:
                logger.debug(f"Plain WS: Session ended for {adapter.addr}")
                if not getattr(websocket, 'closed', False):
                    await websocket.close(1000, "Session ended")
                
        except ConnectionClosed as e:
            logger.info(f"Plain WS: Connection closed: {e}")
        except Exception as e:
            logger.error(f"Plain WS: Error handling client: {e}")
        finally:
            self.active_connections.discard(adapter)