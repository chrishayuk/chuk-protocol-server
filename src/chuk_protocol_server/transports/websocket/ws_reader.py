#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_reader.py
"""
WebSocket Reader Adapter

This module provides a stream reader adapter for WebSocket connections,
translating between the message-based WebSocket API and the stream-based
API used by the telnet server handlers.
"""
import asyncio
import logging
from typing import Optional

# Import WebSocketServerProtocol if available
try:
    from websockets.server import WebSocketServerProtocol
    from websockets.exceptions import ConnectionClosed
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    # Define a placeholder class for type hinting
    class WebSocketServerProtocol:
        pass

# Import base adapter interface
from chuk_protocol_server.transports.transport_adapter import StreamReaderAdapter

# logger
logger = logging.getLogger('chuk-protocol-server')

class WebSocketReader(StreamReaderAdapter):
    """
    Stream reader adapter for WebSocket connections.
    
    This class adapts the WebSocket message-based API to a stream-like
    API that works with the telnet server handlers.
    """
    
    def __init__(self, websocket: WebSocketServerProtocol):
        """
        Initialize the WebSocket reader.
        
        Args:
            websocket: The WebSocket connection
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("WebSockets support not available")
            
        self.websocket = websocket
        self.buffer = bytearray()
        self._eof = False
    
    async def read(self, n: int = -1) -> bytes:
        """
        Read data from the WebSocket.
        
        Args:
            n: Maximum number of bytes to read (-1 for all available)
            
        Returns:
            The data read from the WebSocket, or empty bytes if EOF
        """
        if self._eof and not self.buffer:
            return b''
        
        # If we have enough data in the buffer, return it
        if n != -1 and len(self.buffer) >= n:
            data = bytes(self.buffer[:n])
            self.buffer = self.buffer[n:]
            return data
        
        # Otherwise, we need to receive more data
        try:
            message = await self.websocket.recv()
            
            # Handle different message types
            if isinstance(message, str):
                # Text message - convert to bytes
                self.buffer.extend(message.encode('utf-8'))
            elif isinstance(message, bytes):
                # Binary message - add directly
                self.buffer.extend(message)
            else:
                # Unknown message type
                logger.warning(f"Received unknown message type: {type(message)}")
                return b''
            
            # Now return the requested amount
            if n == -1:
                data = bytes(self.buffer)
                self.buffer.clear()
                return data
            else:
                data = bytes(self.buffer[:n])
                self.buffer = self.buffer[n:]
                return data
                
        except ConnectionClosed:
            # Connection closed by the client
            self._eof = True
            if n == -1:
                # Return whatever is left in the buffer
                data = bytes(self.buffer)
                self.buffer.clear()
                return data
            else:
                # Return up to n bytes
                data = bytes(self.buffer[:n])
                self.buffer = self.buffer[n:]
                return data
    
    async def readline(self) -> bytes:
        """
        Read a complete line from the WebSocket.
        
        Returns:
            A line of data, including the line terminator
        """
        # Look for a newline in the buffer
        nl_index = -1
        for i, byte in enumerate(self.buffer):
            if byte in (10, 13):  # LF or CR
                nl_index = i
                break
        
        if nl_index != -1:
            # We found a newline
            line = bytes(self.buffer[:nl_index+1])
            self.buffer = self.buffer[nl_index+1:]
            
            # Handle CR+LF
            if line[-1] == 13 and self.buffer and self.buffer[0] == 10:
                line += bytes([self.buffer[0]])
                self.buffer = self.buffer[1:]
            
            return line
        
        # No newline in buffer, need to receive more data
        while not self._eof:
            try:
                message = await self.websocket.recv()
                
                # Process the received message
                if isinstance(message, str):
                    message_bytes = message.encode('utf-8')
                elif isinstance(message, bytes):
                    message_bytes = message
                else:
                    logger.warning(f"Received unknown message type: {type(message)}")
                    continue
                
                # Add to buffer and check for newline
                self.buffer.extend(message_bytes)
                
                # Look for a newline in the new data
                for i in range(len(self.buffer) - len(message_bytes), len(self.buffer)):
                    if self.buffer[i] in (10, 13):  # LF or CR
                        # We found a newline, handle it
                        nl_index = i
                        line = bytes(self.buffer[:nl_index+1])
                        self.buffer = self.buffer[nl_index+1:]
                        
                        # Handle CR+LF
                        if line[-1] == 13 and self.buffer and self.buffer[0] == 10:
                            line += bytes([self.buffer[0]])
                            self.buffer = self.buffer[1:]
                        
                        return line
            
            except ConnectionClosed:
                self._eof = True
                break
        
        # If we reach here, we're at EOF
        if self.buffer:
            # Return whatever is left in the buffer
            data = bytes(self.buffer)
            self.buffer.clear()
            return data
        else:
            return b''
    
    def at_eof(self) -> bool:
        """
        Check if the WebSocket is at EOF.
        
        Returns:
            True if the WebSocket is at EOF and the buffer is empty,
            False otherwise
        """
        return self._eof and not self.buffer