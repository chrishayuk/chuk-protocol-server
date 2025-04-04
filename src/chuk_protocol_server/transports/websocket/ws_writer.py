#!/usr/bin/env python3
# chuk_protocol_server/transports/websocket/ws_writer.py
"""
WebSocket Writer Adapter

This module provides a stream writer adapter for WebSocket connections,
translating between the stream-based API used by the telnet server handlers
and the message-based WebSocket API.
"""
import asyncio
import logging
from typing import Any, Optional

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
from chuk_protocol_server.transports.transport_adapter import StreamWriterAdapter

# Configure logging
logger = logging.getLogger('websocket-writer')

class WebSocketWriter(StreamWriterAdapter):
    """
    Stream writer adapter for WebSocket connections.
    
    This class adapts the stream-based writer API used by the telnet server
    handlers to the message-based WebSocket API.
    """
    
    def __init__(self, websocket: WebSocketServerProtocol):
        """
        Initialize the WebSocket writer.
        
        Args:
            websocket: The WebSocket connection
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("WebSockets support not available")
            
        self.websocket = websocket
        self.closed = False
        self._drain_lock = asyncio.Lock()
        self._pending_writes = []
    
    async def write(self, data: bytes) -> None:
        """
        Write data to the WebSocket.
        
        Args:
            data: The data to write
        """
        if self.closed:
            return
        
        try:
            # Queue the write operation
            future = asyncio.create_task(self.websocket.send(data))
            self._pending_writes.append(future)
        except Exception as e:
            logger.error(f"Error writing to WebSocket: {e}")
            # Mark as closed on error
            self.closed = True
            raise
    
    async def drain(self) -> None:
        """
        Ensure all data is sent.
        
        This method waits for all pending write operations to complete.
        """
        if self.closed:
            return
        
        async with self._drain_lock:
            if not self._pending_writes:
                return
            
            # Wait for all pending writes to complete
            try:
                await asyncio.gather(*self._pending_writes)
            except Exception as e:
                logger.error(f"Error draining WebSocket: {e}")
                # Mark as closed on error
                self.closed = True
                raise
            finally:
                # Clear the pending writes list
                self._pending_writes.clear()
    
    def close(self) -> None:
        """
        Mark the WebSocket for closing.
        
        The actual closing happens asynchronously in wait_closed.
        """
        self.closed = True
    
    async def wait_closed(self) -> None:
        """
        Wait until the WebSocket is closed.
        
        This method actually closes the WebSocket if it's not already closed.
        """
        if not self.closed:
            self.close()
        
        try:
            # Ensure all pending writes are completed before closing
            await self.drain()
            
            # Close the WebSocket with a normal closure code
            await self.websocket.close(1000, "Connection closed")
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    
    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """
        Get extra information about the WebSocket connection.
        
        Args:
            name: The name of the information to get
            default: The default value to return if not available
            
        Returns:
            The requested information or the default value
        """
        if name == 'peername':
            return self.websocket.remote_address
        elif name == 'sockname':
            return self.websocket.local_address
        else:
            return default