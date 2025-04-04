#!/usr/bin/env python3
# chuk_protocol_server/handlers/base_handler.py
"""
Base Connection Handler

This module provides the foundational handler for network connections,
with basic I/O operations and connection lifecycle management.
"""
import asyncio
import logging
from typing import Optional, Any

# logger
logger = logging.getLogger('chuk-protocol-server')

class BaseHandler:
    """
    Base class for handling client connections.
    
    This class provides the core functionality for managing a network connection,
    including reading and writing data, and handling the connection lifecycle.
    It is intended to be subclassed by more specific protocol handlers.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the base handler with the given streams.
        
        Args:
            reader: The stream reader for reading from the client.
            writer: The stream writer for writing to the client.
        """
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')
        self.running = True
        self.server = None  # Can be set by the server after creation
        self.session_ended = False  # Flag to indicate the session was ended by handler
    
    async def handle_client(self) -> None:
        """
        Main client handling loop.
        
        This is the main entry point for client handling. Subclasses must
        override this method to implement specific protocol handling.
        
        Raises:
            NotImplementedError: If not overridden by a subclass.
        """
        raise NotImplementedError("Subclasses must implement handle_client")
    
    async def send_raw(self, data: bytes) -> None:
        """
        Send raw data to the client.
        
        This method ensures that if the underlying writer's write method returns a coroutine,
        it is properly awaited. It also calls drain if available.
        
        Args:
            data: The raw data to send.
            
        Raises:
            Exception: If an error occurs while sending data.
        """
        try:
            # Check if writer.write is a coroutine function
            if asyncio.iscoroutinefunction(self.writer.write):
                await self.writer.write(data)
            else:
                result = self.writer.write(data)
                # In some cases, write() might return a coroutine even if not defined as a function,
                # so check the result as well.
                if asyncio.iscoroutine(result):
                    await result

            # Attempt to drain if available. Some async writers (e.g. in websockets) may not have drain.
            drain = getattr(self.writer, "drain", None)
            if drain is not None:
                if asyncio.iscoroutinefunction(drain):
                    await drain()
                else:
                    result = drain()
                    if asyncio.iscoroutine(result):
                        await result
        except Exception as e:
            logger.error(f"Error sending raw data to {self.addr}: {e}")
            raise
    
    async def read_raw(self, n: int = -1, timeout: Optional[float] = None) -> bytes:
        """
        Read raw data from the client with optional timeout.
        
        Args:
            n: Maximum number of bytes to read (-1 for unlimited).
            timeout: Maximum time to wait in seconds (None for no timeout).
            
        Returns:
            The bytes read from the client.
            
        Raises:
            asyncio.TimeoutError: If the timeout expires.
            Exception: If an error occurs while reading data.
        """
        try:
            if timeout is not None:
                return await asyncio.wait_for(self.reader.read(n), timeout=timeout)
            else:
                return await self.reader.read(n)
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Error reading raw data from {self.addr}: {e}")
            raise
    
    async def end_session(self, message: Optional[str] = None) -> None:
        """
        End the client session gracefully.
        
        This method sets the session_ended flag and optionally sends a final message.
        It should be called when the handler decides to end the session, such as
        after a 'quit' command.
        
        Args:
            message: Optional final message to send before ending the session.
        """
        try:
            if message:
                if hasattr(self, 'send_line'):
                    await self.send_line(message)
                else:
                    await self.send_raw((message + "\r\n").encode('utf-8'))
            
            self.session_ended = True
            self.running = False
            
        except Exception as e:
            logger.error(f"Error during session end for {self.addr}: {e}")
    
    async def cleanup(self) -> None:
        """
        Clean up resources when the connection is closed.
        
        This method should be called when the connection is terminated,
        either normally or due to an error.
        """
        try:
            logger.debug(f"Cleaning up connection from {self.addr}")
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error during cleanup for {self.addr}: {e}")
        logger.info(f"Connection closed for {self.addr}")
    
    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """
        Get extra information about the connection.
        
        This is a wrapper around the StreamWriter's get_extra_info method,
        which provides access to transport-specific information.
        
        Args:
            name: The name of the information to get.
            default: The default value to return if the information is not available.
            
        Returns:
            The requested information or the default value.
        """
        return self.writer.get_extra_info(name, default)
    
    async def on_connect(self) -> None:
        """
        Called when a client connects.
        
        This is a hook method that can be overridden by subclasses to perform
        initialization when a client connects.
        """
        logger.debug(f"Client connected from {self.addr}")
    
    async def on_disconnect(self) -> None:
        """
        Called when a client disconnects.
        
        This is a hook method that can be overridden by subclasses to perform
        cleanup when a client disconnects.
        """
        logger.debug(f"Client disconnected from {self.addr}")
    
    async def on_error(self, exception: Exception) -> None:
        """
        Called when an error occurs during client handling.
        
        This is a hook method that can be overridden by subclasses to handle
        errors that occur during client handling.
        
        Args:
            exception: The exception that occurred.
        """
        logger.error(f"Error handling client {self.addr}: {exception}")
    
    def __repr__(self) -> str:
        """
        Return a string representation of the handler.
        
        Returns:
            A string representation of the handler.
        """
        return f"{self.__class__.__name__}(addr={self.addr})"