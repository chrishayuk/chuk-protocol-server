#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_monitorable_reader.py
"""
Monitorable WebSocket Reader

Extends the standard WebSocket reader with monitoring capabilities,
sending client input to the session monitor.
"""
import asyncio
import logging
from typing import Optional

# websockets
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed

# imports
from chuk_protocol_server.transports.websocket.ws_reader import WebSocketReader
from chuk_protocol_server.transports.websocket.ws_session_monitor import SessionMonitor

# logger
logger = logging.getLogger('chuk-protocol-server')

class MonitorableWebSocketReader(WebSocketReader):
    """
    WebSocket reader that broadcasts client input to a session monitor.
    """
    
    def __init__(self, websocket: WebSocketServerProtocol):
        """
        Initialize the monitorable WebSocket reader.
        
        Args:
            websocket: The WebSocket connection
        """
        super().__init__(websocket)
        self.session_id: Optional[str] = None
        self.monitor: Optional[SessionMonitor] = None
    
    async def read(self, n: int = -1) -> bytes:
        """
        Read data from the WebSocket and broadcast it to the monitor.
        
        Args:
            n: Maximum number of bytes to read (-1 for all available)
            
        Returns:
            The data read from the WebSocket, or empty bytes if EOF
        """
        data = await super().read(n)
        
        # Broadcast to monitor if enabled
        if data and self.monitor and self.session_id:
            await self._broadcast_client_input(data)
            
        return data
    
    async def readline(self) -> bytes:
        """
        Read a complete line from the WebSocket and broadcast it to the monitor.
        
        Returns:
            A line of data, including the line terminator
        """
        line = await super().readline()
        
        # Broadcast to monitor if enabled
        if line and self.monitor and self.session_id:
            await self._broadcast_client_input(line)
            
        return line
    
    async def _broadcast_client_input(self, data: bytes) -> None:
        """
        Broadcast client input to the session monitor.
        
        Args:
            data: The data to broadcast
        """
        if not self.monitor or not self.session_id:
            return
            
        try:
            # Try to decode the data as UTF-8 text
            text = data.decode('utf-8', errors='replace')
            
            # Skip empty messages or just whitespace
            if not text.strip():
                return
                
            # Log the message being broadcast for debugging
            logger.debug(f"Broadcasting client input: {repr(text)}")
            
            # Broadcast to the monitor
            await self.monitor.broadcast_session_event(
                self.session_id,
                'client_input',
                {'text': text}
            )
        except Exception as e:
            logger.error(f"Error broadcasting client input: {e}")