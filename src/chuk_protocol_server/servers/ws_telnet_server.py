#!/usr/bin/env python3
# chuk_protocol_server/servers/ws_telnet_server.py
"""
WebSocket Telnet Server with Session Monitoring

This server accepts WebSocket connections and performs Telnet negotiation
over the WebSocket transport. It adapts the WebSocket connection to behave
like a Telnet connection and supports monitoring sessions if enabled.
"""
import asyncio
import logging
import uuid
from typing import Type, List, Optional

import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

from urllib.parse import urlparse

from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter
from chuk_protocol_server.servers.base_ws_server import BaseWebSocketServer

logger = logging.getLogger('chuk-protocol-server')

class WSTelnetServer(BaseWebSocketServer):
    """
    WebSocket Telnet server that performs Telnet negotiation over WebSocket.
    Supports monitoring sessions through a separate endpoint if enabled.
    """
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8026,
        handler_class: Type[BaseHandler] = None,
        path: Optional[str] = '/ws_telnet',  # if None, accept all paths
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: Optional[List[str]] = None,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
        enable_monitoring: bool = False,
        monitor_path: str = '/monitor'
    ):
        """
        Initialize the WebSocket Telnet server.
        """
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
        self.transport = "ws_telnet"

    async def _connection_handler(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle an incoming WebSocket connection for Telnet negotiation.
        This checks the requested path, performs CORS checks, and then uses a
        WebSocketAdapter to invoke the Telnet handler logic.
        """
        # Check if this is a monitoring connection.
        if self.enable_monitoring and self.session_monitor:
            try:
                request_path = websocket.request.path
                if self.session_monitor.is_monitor_path(request_path):
                    logger.info(f"Monitoring viewer connected: {websocket.remote_address}")
                    await self.session_monitor.handle_viewer_connection(websocket)
                    return
            except AttributeError:
                logger.error("WS Telnet: websocket.request.path not available")
        
        # Reject connection if we're at max connections.
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
            logger.error("WS Telnet: websocket.request.path not available")
            await websocket.close(code=1011, reason="Internal server error")
            return

        # Validate the path if a fixed path is set.
        if self.path is not None:
            parsed_path = urlparse(raw_path)
            actual_path = parsed_path.path or "/"
            expected_path = self.path if self.path.startswith("/") else f"/{self.path}"
            logger.debug(f"WS Telnet: raw_path='{raw_path}', actual_path='{actual_path}', expected prefix='{expected_path}'")
            if not actual_path.startswith(expected_path):
                logger.warning(f"WS Telnet: Rejected connection: path '{raw_path}' does not start with expected prefix '{expected_path}'")
                await websocket.close(code=1003, reason=f"Endpoint {raw_path} not found")
                return
            websocket.full_path = raw_path
        else:
            logger.debug("WS Telnet: path is None => accepting any path")

        # Optional CORS check.
        try:
            headers = getattr(websocket, "request_headers", {})
            origin = headers.get("Origin") or headers.get("origin") or headers.get("HTTP_ORIGIN", "")
            if origin and self.allow_origins and ('*' not in self.allow_origins) and (origin not in self.allow_origins):
                logger.warning(f"WS Telnet: Origin '{origin}' not allowed")
                await websocket.close(code=403, reason="Origin not allowed")
                return
        except Exception as err:
            logger.error(f"WS Telnet: CORS check error: {err}")
            await websocket.close(code=1011, reason="Internal server error")
            return

        # Create the adapter (use a monitorable adapter if monitoring is enabled).
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
            logger.debug(f"Created monitorable Telnet adapter with session ID: {adapter.session_id}")
        else:
            adapter = WebSocketAdapter(websocket, self.handler_class)
            
        adapter.server = self
        # In ws_telnet mode, let Telnet negotiation proceed.
        adapter.mode = "telnet"
        
        # Pass welcome message if configured.
        if self.welcome_message:
            adapter.welcome_message = self.welcome_message
            
        self.active_connections.add(adapter)
        try:
            if self.connection_timeout:
                try:
                    await asyncio.wait_for(adapter.handle_client(), timeout=self.connection_timeout)
                except asyncio.TimeoutError:
                    logger.info(f"Connection timeout ({self.connection_timeout}s) for {adapter.addr}")
            else:
                await adapter.handle_client()
                
            if hasattr(adapter.handler, 'session_ended') and adapter.handler.session_ended:
                logger.debug(f"WS Telnet: Session ended for {adapter.addr}")
                if not getattr(websocket, 'closed', False):
                    await websocket.close(1000, "Session ended")
                    
        except ConnectionClosed as e:
            logger.info(f"WS Telnet: Connection closed: {e}")
        except Exception as e:
            logger.error(f"WS Telnet: Error handling client: {e}")
        finally:
            self.active_connections.discard(adapter)