#!/usr/bin/env python3
# chuk_protocol_server/servers/base_ws_server.py
"""
Base WebSocket Server with Monitoring Support

Provides a base class for WebSocket servers that run over the 'websockets' package.
Implements common functionality including session monitoring capability.
"""
import asyncio
import logging
import ssl
import uuid
from typing import Type, List, Optional, Any, Dict, Set
from abc import abstractmethod

# websockets
import websockets
from websockets.server import WebSocketServerProtocol

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_server import BaseServer
from chuk_protocol_server.transports.websocket.ws_session_monitor import SessionMonitor
from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter

# logger
logger = logging.getLogger('chuk-protocol-server')

class BaseWebSocketServer(BaseServer):
    """
    Base class for WebSocket servers. Handles common WebSocket functionality.
    Supports session monitoring if enabled.
    Subclasses must implement the _connection_handler method.
    """
    
    def __init__(
        self,
        host: str = '0.0.0.0',
        port: int = 8025,
        handler_class: Type[BaseHandler] = None,
        ping_interval: int = 30,
        ping_timeout: int = 10,
        allow_origins: Optional[List[str]] = None,
        ssl_cert: Optional[str] = None,
        ssl_key: Optional[str] = None,
        enable_monitoring: bool = False,
        monitor_path: str = '/monitor'
    ):
        """
        Initialize the WebSocket server.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
            ping_interval: Interval between WebSocket ping frames
            ping_timeout: Timeout for WebSocket ping responses
            allow_origins: List of allowed origins for CORS
            ssl_cert: Path to SSL certificate file
            ssl_key: Path to SSL key file
            enable_monitoring: Whether to enable session monitoring
            monitor_path: Path for the monitoring WebSocket endpoint
        """
        super().__init__(host, port, handler_class)
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.allow_origins = allow_origins or ['*']
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.ssl_context = None
        
        # Session monitoring configuration
        self.enable_monitoring = enable_monitoring
        self.session_monitor = None
        self.monitor_path = monitor_path
        
        if enable_monitoring:
            self.session_monitor = SessionMonitor(path=monitor_path)
            logger.info(f"Session monitoring enabled on path: {monitor_path}")
        
        # Set up SSL context if certificates provided
        if ssl_cert and ssl_key:
            self.ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            self.ssl_context.load_cert_chain(ssl_cert, ssl_key)
            logger.info(f"SSL enabled with cert: {ssl_cert}")

    async def start_server(self) -> None:
        """
        Start the WebSocket server.
        
        This method starts the server listening for connections
        on the specified host and port.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        await super().start_server()
        try:
            self.server = await self._create_server()
            
            scheme = "wss" if self.ssl_context else "ws"
            logger.info(f"WebSocket server running on {scheme}://{self.host}:{self.port}")
            
            # Keep the server running
            await self._keep_running()
        except Exception as e:
            logger.error(f"Error starting WebSocket server: {e}")
            raise

    async def _create_server(self) -> Any:
        """
        Create the WebSocket server instance.
        
        Returns:
            The WebSocket server instance
        """
        return await websockets.serve(
            self._connection_handler,
            self.host,
            self.port,
            ssl=self.ssl_context,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            compression=None,
            close_timeout=10
        )

    async def _keep_running(self) -> None:
        """
        Keep the server running until shutdown is requested.
        """
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("WebSocket server task cancelled")
            await self.shutdown()

    async def _close_server(self) -> None:
        """
        Close the WebSocket server.
        """
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def _force_close_connections(self) -> None:
        """
        Force close all remaining WebSocket connections.
        """
        for adapter in list(self.active_connections):
            try:
                await adapter.close()
                self.active_connections.remove(adapter)
            except Exception as e:
                logger.error(f"Error force closing WebSocket connection: {e}")

    @abstractmethod
    async def _connection_handler(self, websocket: WebSocketServerProtocol) -> None:
        """
        Handle a new WebSocket connection.
        
        This method must be implemented by subclasses to handle
        WebSocket-specific connection setup and processing.
        
        Args:
            websocket: The WebSocket connection
        """
        pass