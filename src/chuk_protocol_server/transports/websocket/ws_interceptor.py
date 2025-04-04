#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_interceptor.py
"""
WebSocket Message Interceptor

Provides a proxy-like wrapper around WebSocket connections to intercept
and monitor all messages at the protocol level.
"""
import asyncio
import logging
from typing import Optional, Dict, Any

# websockets
import websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# imports
from chuk_protocol_server.transports.websocket.ws_session_monitor import SessionMonitor

# logger
logger = logging.getLogger('chuk-protocol-server')

class WebSocketInterceptor:
    """
    Intercepts WebSocket messages at the protocol level.
    
    This class wraps a WebSocket connection to monitor all 
    messages sent and received.
    """
    
    def __init__(
        self, 
        websocket: WebSocketServerProtocol, 
        session_id: str,
        monitor: Optional[SessionMonitor] = None
    ):
        """
        Initialize the WebSocket interceptor.
        
        Args:
            websocket: The WebSocket connection to intercept
            session_id: The unique session ID
            monitor: The monitor to broadcast events to
        """
        self.websocket = websocket
        self.session_id = session_id
        self.monitor = monitor
    
    async def recv(self) -> Any:
        """
        Receive a message from the WebSocket.
        
        This intercepts the message and broadcasts it to the monitor
        before returning it to the caller.
        
        Returns:
            The received message
        """
        message = await self.websocket.recv()
        
        # Broadcast the message to the monitor
        if self.monitor:
            try:
                # Handle different message types
                if isinstance(message, str):
                    text = message
                elif isinstance(message, bytes):
                    text = message.decode('utf-8', errors='replace')
                else:
                    text = str(message)
                
                logger.debug(f"Intercepted client message: {repr(text)}")
                
                # Broadcast to the monitor
                await self.monitor.broadcast_session_event(
                    self.session_id,
                    'client_input',
                    {'text': text}
                )
            except Exception as e:
                logger.error(f"Error broadcasting intercepted client message: {e}")
        
        return message
    
    async def send(self, message: Any) -> None:
        """
        Send a message to the WebSocket.
        
        This intercepts the message and broadcasts it to the monitor
        before sending it to the client.
        
        Args:
            message: The message to send
        """
        # Broadcast the message to the monitor
        if self.monitor:
            try:
                # Handle different message types
                if isinstance(message, str):
                    text = message
                elif isinstance(message, bytes):
                    text = message.decode('utf-8', errors='replace')
                else:
                    text = str(message)
                
                logger.debug(f"Intercepted server message: {repr(text)}")
                
                # Broadcast to the monitor
                await self.monitor.broadcast_session_event(
                    self.session_id,
                    'server_message',
                    {'text': text}
                )
            except Exception as e:
                logger.error(f"Error broadcasting intercepted server message: {e}")
        
        # Send the message to the client
        await self.websocket.send(message)
    
    async def __aiter__(self):
        """
        Iterate over messages from the WebSocket.
        
        This allows the interceptor to be used in an async for loop.
        """
        try:
            while True:
                yield await self.recv()
        except ConnectionClosed:
            return
    
    # Forward other attributes to the underlying WebSocket
    def __getattr__(self, name):
        return getattr(self.websocket, name)