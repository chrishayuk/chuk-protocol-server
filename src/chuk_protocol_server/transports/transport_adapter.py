#!/usr/bin/env python3
# chuk_protocol_server/transports/transport_adapter.py
"""
Base Transport Adapter Interface

This module defines the interfaces that all transport adapters must implement
to work with the telnet server handlers. It provides the foundation for
creating transport-specific adapters.
"""
import asyncio
import logging
from typing import Any, Dict, Optional, Tuple, Type

# Import base handler
from chuk_protocol_server.handlers.base_handler import BaseHandler

# logger
logger = logging.getLogger('chuk-protocol-server')

class StreamReaderAdapter:
    """
    Base interface for stream reader adapters.
    
    This class defines the interface that all reader adapters must
    implement to work with the handler classes.
    """
    
    async def read(self, n: int = -1) -> bytes:
        """
        Read data from the transport.
        
        Args:
            n: Maximum number of bytes to read
            
        Returns:
            The data read from the transport
        """
        raise NotImplementedError("Subclasses must implement read")
    
    async def readline(self) -> bytes:
        """
        Read a complete line from the transport.
        
        Returns:
            A line of data, including the line terminator
        """
        raise NotImplementedError("Subclasses must implement readline")
    
    def at_eof(self) -> bool:
        """
        Check if the transport is at EOF.
        
        Returns:
            True if the transport is at EOF, False otherwise
        """
        raise NotImplementedError("Subclasses must implement at_eof")


class StreamWriterAdapter:
    """
    Base interface for stream writer adapters.
    
    This class defines the interface that all writer adapters must
    implement to work with the handler classes.
    """
    
    async def write(self, data: bytes) -> None:
        """
        Write data to the transport.
        
        Args:
            data: The data to write
        """
        raise NotImplementedError("Subclasses must implement write")
    
    async def drain(self) -> None:
        """Ensure all data is sent."""
        raise NotImplementedError("Subclasses must implement drain")
    
    def close(self) -> None:
        """Close the transport."""
        raise NotImplementedError("Subclasses must implement close")
    
    async def wait_closed(self) -> None:
        """Wait until the transport is closed."""
        raise NotImplementedError("Subclasses must implement wait_closed")
    
    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """
        Get extra information about the transport.
        
        Args:
            name: The name of the information to get
            default: The default value to return if not available
            
        Returns:
            The requested information or the default value
        """
        return default


class BaseTransportAdapter:
    """
    Base class for transport adapters.
    
    This class defines the common interface that all transport adapters
    must implement to work with the server framework.
    """
    
    def __init__(self, handler_class: Type[BaseHandler]):
        """
        Initialize the transport adapter.
        
        Args:
            handler_class: The handler class to use
        """
        self.handler_class = handler_class
        self.server = None  # Will be set by the server
    
    async def handle_client(self) -> None:
        """
        Handle a client connection.
        
        This method should create a handler instance for the client and
        delegate to its handle_client method.
        """
        raise NotImplementedError("Subclasses must implement handle_client")
    
    async def send_line(self, message: str) -> None:
        """
        Send a line of text to the client.
        
        Args:
            message: The message to send
        """
        raise NotImplementedError("Subclasses must implement send_line")
    
    async def close(self) -> None:
        """Close the connection."""
        raise NotImplementedError("Subclasses must implement close")