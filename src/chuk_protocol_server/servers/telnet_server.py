#!/usr/bin/env python3
# chuk_protocol_server/servers/telnet_server.py
"""
Telnet Server Module

Core telnet server implementation with connection management.
This module provides the foundation for hosting telnet services
with proper connection lifecycle management and graceful shutdown.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Set, List, Type

# Import the protocol handler and base server
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_server import BaseServer

# Import Telnet constants (IAC, etc.) used for negotiation detection
from chuk_protocol_server.protocols.telnet.constants import IAC

# logger
logger = logging.getLogger('chuk-protocol-server')

class TelnetServer(BaseServer):
    """
    Telnet server with connection handling capabilities.
    
    This class manages the lifecycle of a telnet server, including
    starting and stopping the server, handling client connections,
    and providing utilities for server-wide operations.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023, 
                 handler_class: Type[BaseHandler] = None):
        """
        Initialize the telnet server with host, port, and handler class.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
        """
        super().__init__(host, port, handler_class)
        self.transport = "telnet"
    
    async def start_server(self) -> None:
        """
        Start the telnet server.
        
        This method starts the server listening for connections
        on the specified host and port.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        # Call the base implementation to validate handler class
        await super().start_server()
        
        try:
            self.server = await self._create_server()
            
            addr = self.server.sockets[0].getsockname()
            logger.info(f"Telnet server running on {addr[0]}:{addr[1]}")
            
            async with self.server:
                await self.server.serve_forever()
        except Exception as e:
            logger.error(f"Error starting telnet server: {e}")
            raise
    
    async def _create_server(self) -> asyncio.Server:
        """
        Create the asyncio server instance.
        
        Returns:
            The asyncio server instance
        """
        return await asyncio.start_server(
            self.handle_new_connection,
            self.host,
            self.port
        )
    
    async def handle_new_connection(self, reader: asyncio.StreamReader, 
                                   writer: asyncio.StreamWriter) -> None:
        """
        Handle a new client connection.
        
        This method creates a handler instance for the new client,
        adds it to the active connections, and starts processing.
        It first attempts to detect if Telnet negotiation is taking place.
        If not, it falls back into a simplified text mode.
        
        Args:
            reader: The stream reader for the client
            writer: The stream writer for the client
        """
        negotiation_mode = "telnet"  # default to full telnet mode
        initial_data = b""
        try:
            # Attempt to read a few bytes within a short timeout (e.g. 1 second)
            initial_data = await asyncio.wait_for(reader.read(10), timeout=1.0)
        except asyncio.TimeoutError:
            # No data received within timeout; assume simple mode
            negotiation_mode = "simple"
        else:
            if not initial_data or initial_data[0] != IAC:
                # Data does not start with the IAC byte, so negotiation likely won't occur
                negotiation_mode = "simple"
        
        logger.debug(f"Detected connection mode: {negotiation_mode}")
        
        # Create handler and store the initial data and mode.
        handler = self.create_handler(reader, writer)
        # Attach the detected mode and any initial data (if you want to process it later)
        handler.mode = negotiation_mode
        handler.initial_data = initial_data
        
        # Continue with standard connection handling
        await super().handle_new_connection(reader, writer)