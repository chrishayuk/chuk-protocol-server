#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_adapter.py
"""
WebSocket Transport Adapter

This module provides a transport adapter for WebSocket connections,
bridging between WebSocket clients and the telnet server handlers.
"""
import asyncio
import logging
from typing import Optional, Type

# websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.transports.transport_adapter import BaseTransportAdapter
from chuk_protocol_server.transports.websocket.ws_reader import WebSocketReader
from chuk_protocol_server.transports.websocket.ws_writer import WebSocketWriter

# logger
logger = logging.getLogger('chuk-protocol-server')

class WebSocketAdapter(BaseTransportAdapter):
    """
    Transport adapter for WebSocket connections.
    
    This class adapts WebSocket connections to work with the telnet
    server handlers, implementing the necessary bridging logic.
    """
    
    def __init__(self, websocket: WebSocketServerProtocol, 
                 handler_class: Type[BaseHandler]):
        """
        Initialize the WebSocket adapter.
        
        Args:
            websocket: The WebSocket connection
            handler_class: The handler class to use
        """
        super().__init__(handler_class)
        self.websocket = websocket
        self.reader = WebSocketReader(websocket)
        self.writer = WebSocketWriter(websocket)
        self.handler = None
        self.addr = websocket.remote_address

        # You can default to "telnet" or "simple" here, or let your server set it.
        # For a "plain" WebSocket scenario, your server might do `adapter.mode = "simple"`.
        # For a Telnet-over-WebSocket scenario, `adapter.mode = "telnet"`.
        self.mode = "simple"  # Default; set to "simple" if you want no negotiation.
        
        # Custom welcome message that can be passed from the server
        self.welcome_message = None
    
    async def handle_client(self) -> None:
        """
        Handle a WebSocket client connection.
        
        This method creates a handler instance for the client and
        delegates to its handle_client method.
        """
        # Create the handler
        self.handler = self.handler_class(self.reader, self.writer)
        
        # If a server is set, also attach it to the server
        if self.server:
            self.handler.server = self.server
        
        # IMPORTANT: Set the handler's mode to the adapter's mode
        self.handler.mode = self.mode
        
        # Pass welcome message if available and the handler supports it
        if self.welcome_message and hasattr(self.handler, 'welcome_message'):
            self.handler.welcome_message = self.welcome_message
        
        try:
            await self.handler.handle_client()
        except ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket client: {e}")
            # Re-raise to allow the server to handle it
            raise
    
    async def send_line(self, message: str) -> None:
        """
        Send a line of text to the client.
        
        Args:
            message: The message to send
        """
        if self.handler and hasattr(self.handler, 'send_line'):
            await self.handler.send_line(message)
        else:
            try:
                await self.writer.write((message + '\r\n').encode('utf-8'))
                await self.writer.drain()
            except Exception as e:
                logger.error(f"Error sending message to WebSocket client: {e}")
    
    async def close(self) -> None:
        """Close the WebSocket connection."""
        try:
            if self.handler and hasattr(self.handler, 'cleanup'):
                await self.handler.cleanup()
            
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing WebSocket adapter: {e}")