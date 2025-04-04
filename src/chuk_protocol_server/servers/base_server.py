#!/usr/bin/env python3
# chuk_protocol_server/servers/base_server.py
"""
Base Server Interface

This module defines the abstract base class that all server implementations
must inherit from to work with the telnet server framework. It provides common
functionality and enforces a consistent interface across different transports.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, Type, List

# Import base handler
from chuk_protocol_server.handlers.base_handler import BaseHandler

# logger
logger = logging.getLogger('chuk-protocol-server')

class BaseServer(ABC):
    """
    Abstract base class for server implementations.
    
    This class defines the common interface and functionality that all
    server implementations must provide, ensuring consistency across
    different transport protocols.
    """
    
    def __init__(self, host: str = '0.0.0.0', port: int = 8023,
                 handler_class: Type[BaseHandler] = None):
        """
        Initialize the server with host, port, and handler class.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
            handler_class: Handler class to use for client connections
        """
        self.host = host
        self.port = port
        self.handler_class = handler_class
        self.server = None
        self.active_connections = set()
        self.running = True
        self.signals_registered = False
        
        # Common configuration parameters with default values
        self.max_connections = 100
        self.connection_timeout = 300
        self.welcome_message = None
    
    @abstractmethod
    async def start_server(self) -> None:
        """
        Start the server.
        
        This method should start the server listening for connections
        on the specified host and port.
        
        Raises:
            ValueError: If no handler class was provided
            Exception: If an error occurs while starting the server
        """
        # Validate handler class is provided
        if not self.handler_class:
            raise ValueError("Handler class must be provided")
    
    @abstractmethod
    async def _create_server(self) -> Any:
        """
        Create the server instance specific to the transport type.
        
        This method must be implemented by subclasses to create the 
        appropriate server for the transport.
        
        Returns:
            The server instance.
        """
        pass
    
    async def handle_new_connection(self, reader, writer) -> None:
        """
        Handle a new client connection.
        
        This method creates a handler instance for the new client,
        adds it to the active connections, and starts processing.
        
        Args:
            reader: The stream reader for the client
            writer: The stream writer for the client
        """
        # Check connection limit
        if self.max_connections and len(self.active_connections) >= self.max_connections:
            try:
                logger.warning(f"Maximum connections ({self.max_connections}) reached, rejecting new connection")
                writer.write(b"Server is at maximum capacity. Please try again later.\r\n")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return
            except Exception as e:
                logger.error(f"Error rejecting connection: {e}")
                return
        
        # Create a handler
        handler = self.create_handler(reader, writer)
        
        # Add to active connections
        self.active_connections.add(handler)
        
        try:
            # Delegate client handling to the handler's logic.
            await self.handle_client(handler)
        except Exception as e:
            addr = getattr(handler, 'addr', 'unknown')
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            # Clean up the connection
            await self.cleanup_connection(handler)
            
            # Remove from active connections
            if handler in self.active_connections:
                self.active_connections.remove(handler)
    
    def create_handler(self, reader, writer) -> BaseHandler:
        """
        Create a handler instance for a new connection.
        
        Args:
            reader: The stream reader for the client
            writer: The stream writer for the client
            
        Returns:
            The created handler instance
        """
        handler = self.handler_class(reader, writer)
        handler.server = self  # Set reference to server
        
        # Set welcome message if configured
        if self.welcome_message and hasattr(handler, 'welcome_message'):
            handler.welcome_message = self.welcome_message
            
        return handler
    
    async def handle_client(self, handler: BaseHandler) -> None:
        """
        Handle a client using the handler.
        
        This method delegates client handling to the handler's
        handle_client method.
        
        Args:
            handler: The handler for the client
            
        Raises:
            NotImplementedError: If the handler doesn't implement handle_client
        """
        if hasattr(handler, 'handle_client'):
            # If connection_timeout is set, create a timeout wrapper
            if self.connection_timeout:
                try:
                    await asyncio.wait_for(handler.handle_client(), timeout=self.connection_timeout)
                except asyncio.TimeoutError:
                    logger.info(f"Connection timeout ({self.connection_timeout}s) for {handler.addr}")
            else:
                await handler.handle_client()
        else:
            raise NotImplementedError("Handler must implement handle_client method")
    
    async def cleanup_connection(self, handler: BaseHandler) -> None:
        """
        Clean up a connection.
        
        This method delegates connection cleanup to the handler's
        cleanup method and ensures the writer is properly closed.
        
        Args:
            handler: The handler for the client
        """
        try:
            # Call handler cleanup if available
            if hasattr(handler, 'cleanup'):
                await handler.cleanup()
            
            # Close the writer
            if hasattr(handler, 'writer'):
                handler.writer.close()
                try:
                    await asyncio.wait_for(handler.writer.wait_closed(), timeout=5.0)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error cleaning up client connection: {e}")
    
    async def send_global_message(self, message: str) -> None:
        """
        Send a message to all connected clients.
        
        This method sends a message to all active connections,
        which can be useful for broadcasts or server-wide notifications.
        
        Args:
            message: The message to send
        """
        send_tasks = []
        for handler in self.active_connections:
            try:
                if hasattr(handler, 'send_line'):
                    send_tasks.append(asyncio.create_task(handler.send_line(message)))
            except Exception as e:
                logger.error(f"Error preparing to send message to client: {e}")
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
    
    async def shutdown(self) -> None:
        """
        Gracefully shut down the server.
        
        This method stops accepting new connections, notifies all
        clients of the shutdown, and closes all active connections.
        """
        if not self.running:
            return  # Already shut down
            
        logger.info(f"Shutting down {self.__class__.__name__}...")
        
        # Signal all connections to stop
        self.running = False
        
        # Send shutdown message
        await self.send_global_message("\nServer is shutting down. Goodbye!")
        
        # Close the server
        await self._close_server()
        
        # Wait for connections to close (with timeout)
        await self._wait_for_connections_to_close()
        
        logger.info(f"{self.__class__.__name__} has shut down.")
    
    async def _close_server(self) -> None:
        """
        Close the server to stop accepting new connections.
        
        This method should be called during shutdown to ensure
        the server stops accepting new connections.
        """
        if self.server:
            if hasattr(self.server, 'close'):
                self.server.close()
            
            if hasattr(self.server, 'wait_closed') and callable(self.server.wait_closed):
                await self.server.wait_closed()
    
    async def _wait_for_connections_to_close(self, timeout: int = 5) -> None:
        """
        Wait for active connections to close.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        for i in range(timeout):
            if not self.active_connections:
                break
            logger.info(f"Waiting for connections to close: {len(self.active_connections)} remaining ({timeout-i}s)")
            await asyncio.sleep(1)
        
        # Force close any remaining connections
        if self.active_connections:
            logger.warning(f"Forcing closure of {len(self.active_connections)} remaining connections")
            await self._force_close_connections()
    
    async def _force_close_connections(self) -> None:
        """
        Force close all remaining connections.
        
        This method forcibly closes any connections that didn't
        close gracefully during shutdown.
        """
        for handler in list(self.active_connections):
            try:
                if hasattr(handler, 'writer'):
                    handler.writer.close()
                self.active_connections.remove(handler)
            except Exception as e:
                logger.error(f"Error force closing connection: {e}")
    
    def get_connection_count(self) -> int:
        """
        Get the number of active connections.
        
        Returns:
            The number of active connections
        """
        return len(self.active_connections)
    
    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the server.
        
        Returns:
            A dictionary containing server information
        """
        return {
            'type': self.__class__.__name__,
            'host': self.host,
            'port': self.port,
            'connections': self.get_connection_count(),
            'running': self.running,
            'max_connections': self.max_connections,
            'connection_timeout': self.connection_timeout
        }