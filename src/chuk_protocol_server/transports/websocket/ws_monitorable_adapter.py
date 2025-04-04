#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_monitorable_adapter.py
"""
Monitorable WebSocket Adapter

This module provides a WebSocket adapter with monitoring capabilities
that extends the standard adapter to track and broadcast client activities.
"""
import logging
import uuid
from typing import Optional, Type

# websockets
from websockets.server import WebSocketServerProtocol

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
from chuk_protocol_server.transports.websocket.ws_writer import WebSocketWriter

# Create a monitorable reader instead of the standard one
from chuk_protocol_server.transports.websocket.ws_monitorable_reader import MonitorableWebSocketReader

# logger
logger = logging.getLogger('chuk-protocol-server')


class MonitorableWebSocketAdapter(WebSocketAdapter):
    """
    WebSocket adapter with session monitoring capabilities.
    
    This class extends the standard WebSocketAdapter to add session
    monitoring functionality.
    """
    
    def __init__(self, websocket: WebSocketServerProtocol, handler_class: Type[BaseHandler]):
        """
        Initialize the monitorable WebSocket adapter.
        
        Args:
            websocket: The WebSocket connection
            handler_class: The handler class to use
        """
        self.websocket = websocket
        self.reader = MonitorableWebSocketReader(websocket)
        self.writer = WebSocketWriter(websocket)
        self.handler_class = handler_class
        self.handler = None
        self.addr = websocket.remote_address
        
        # Default to telnet mode (can be changed later)
        self.mode = "telnet"
        
        # Monitoring setup
        self.session_id = str(uuid.uuid4())
        self.monitor = None  # Will be set by the server
        self.is_monitored = False
        
        # Pass monitoring info to the reader
        if hasattr(self.reader, 'session_id'):
            self.reader.session_id = self.session_id
        
        # Server reference (will be set later)
        self.server = None
        
        # Custom welcome message that can be passed from the server
        self.welcome_message = None

    async def handle_client(self) -> None:
        """
        Handle a client connection with monitoring.
        
        This overrides the base handle_client method to add session
        monitoring functionality.
        """
        # Register the session if monitoring is enabled
        if self.monitor and self.is_monitored:
            # Pass monitor to reader
            if hasattr(self.reader, 'monitor'):
                self.reader.monitor = self.monitor
            
            # Get client info
            client_info = {
                'remote_addr': self.websocket.remote_address,
                'path': getattr(self.websocket.request, 'path', 'unknown'),
                'user_agent': getattr(getattr(self.websocket, 'request_headers', {}), 'get', lambda x, y: 'unknown')('User-Agent', 'unknown')
            }
            
            # Register the session
            await self.monitor.register_session(self.session_id, client_info)
        
        try:
            # Create the handler
            self.handler = self.handler_class(self.reader, self.writer)
            
            # If a server is set, also attach it to the handler
            if self.server:
                self.handler.server = self.server
            
            # Set the handler's mode to the adapter's mode
            self.handler.mode = self.mode
            
            # Pass welcome message if available and the handler supports it
            if self.welcome_message and hasattr(self.handler, 'welcome_message'):
                self.handler.welcome_message = self.welcome_message
            
            # Handle the client
            await self.handler.handle_client()
        finally:
            # Unregister the session if monitoring is enabled
            if self.monitor and self.is_monitored:
                await self.monitor.unregister_session(self.session_id)
    
    async def send_line(self, message: str) -> None:
        """
        Send a line of text to the client.
        
        This overrides the base send_line method to add monitoring.
        
        Args:
            message: The message to send
        """
        # Broadcast the outgoing message if monitoring is enabled
        if self.monitor and self.is_monitored:
            logger.debug(f"Broadcasting server message: {repr(message)}")
            await self.monitor.broadcast_session_event(
                self.session_id, 
                'server_message', 
                {'text': message}
            )
        
        # Send to client
        if self.handler and hasattr(self.handler, 'send_line'):
            await self.handler.send_line(message)
        else:
            try:
                await self.writer.write((message + '\r\n').encode('utf-8'))
                await self.writer.drain()
            except Exception as e:
                logger.error(f"Error sending message to WebSocket client: {e}")
                
    async def write(self, data: bytes) -> None:
        """
        Write data directly to the WebSocket.
        
        This captures and broadcasts all raw writes to the client.
        
        Args:
            data: The data to write
        """
        if self.monitor and self.is_monitored:
            try:
                text = data.decode('utf-8', errors='replace')
                if text.strip():
                    await self.monitor.broadcast_session_event(
                        self.session_id,
                        'server_message',
                        {'text': text}
                    )
            except Exception as e:
                logger.error(f"Error broadcasting raw write data: {e}")
        
        await self.writer.write(data)
    
    def __getattr__(self, name):
        """
        Forward attribute lookups to the underlying WebSocket.
        """
        return getattr(self.websocket, name)