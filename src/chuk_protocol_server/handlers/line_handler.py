#!/usr/bin/env python3
# chuk_protocol_server/handlers/line_handler.py
"""
Line Protocol Handler

This module provides a handler for line-by-line input processing,
which is appropriate for applications that process entire commands
at once, such as traditional command-line interfaces.
"""
import asyncio
import logging
from typing import Optional

# imports
from chuk_protocol_server.handlers.character_handler import CharacterHandler

# logger
logger = logging.getLogger('chuk-protocol-server')

class LineHandler(CharacterHandler):
    """
    Handles line-by-line input processing.
    
    This class extends the CharacterHandler to provide line-by-line input
    processing, which is appropriate for applications that process entire
    commands at once rather than responding to individual keystrokes.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the line handler.
        
        Args:
            reader: The stream reader for reading from the client
            writer: The stream writer for writing to the client
        """
        super().__init__(reader, writer)
    
    async def handle_client(self) -> None:
        """
        Main client handling loop for line mode.
        
        This method reads lines one by one and processes them
        by calling the process_line method.
        """
        try:
            await self.on_connect()
            
            # Send welcome message
            await self.send_welcome()
            
            # Main processing loop
            while self.running:
                try:
                    # Read a complete line
                    line = await self.read_line()
                    
                    # Check if the connection was closed
                    if line is None:
                        logger.debug(f"Client {self.addr} disconnected")
                        break
                    
                    # Process the line
                    should_continue = await self.process_line(line)
                    if not should_continue:
                        break
                except asyncio.CancelledError:
                    # The task was cancelled - exit gracefully
                    logger.debug(f"Client handling task for {self.addr} was cancelled")
                    break
                except Exception as e:
                    # Handle other exceptions
                    await self.on_error(e)
                    # Decide whether to continue or break based on the error
                    if "Connection reset" in str(e) or "Broken pipe" in str(e):
                        break
                    # For other errors, wait a bit to avoid spamming logs
                    await asyncio.sleep(1)
        finally:
            # Clean up
            await self.on_disconnect()
            await self.cleanup()
    
    async def read_line(self, timeout: float = 300) -> Optional[str]:
        """
        Read a complete line from the client.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            The line read (without line endings), or None if the connection is closed
            
        Raises:
            asyncio.TimeoutError: If the timeout expires
        """
        try:
            # Read a line (readline includes the delimiter)
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            
            # Check if the connection was closed
            if not data:
                return None
            
            # Decode and strip line endings
            line = data.decode('utf-8', errors='ignore').rstrip('\r\n')
            logger.debug(f"Line read: {repr(line)}")
            return line
        except UnicodeDecodeError:
            # Handle invalid UTF-8
            logger.warning(f"Invalid UTF-8 sequence from {self.addr}")
            return "�"  # Unicode replacement character
        except asyncio.TimeoutError:
            # Let the caller handle timeout
            logger.debug(f"Timeout reading line from {self.addr}")
            raise
        except Exception as e:
            logger.error(f"Error reading line from {self.addr}: {e}")
            return None
    
    async def process_line(self, line: str) -> bool:
        """
        Process a complete line of input.
        
        This is the core method for line-by-line processing.
        Subclasses should override this method to implement specific
        line processing logic.
        
        Args:
            line: The line to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        # Default implementation calls on_command_submitted
        logger.debug(f"Processing line: {repr(line)}")
        
        # Check for exit commands
        if line.lower() in ["exit", "quit", "q"]:
            await self.send_line("Goodbye!")
            return False
        
        # Process the line if not empty
        if line.strip():
            await self.on_command_submitted(line)
        
        # Show the prompt again
        await self.show_prompt()
        return True
    
    async def send_welcome(self) -> None:
        """
        Send a welcome message to the client.
        
        This is a hook method that can be overridden by subclasses to
        send a custom welcome message.
        """
        await self.send_line("Welcome to Line Mode")
        await self.show_prompt()
    
    async def process_character(self, char: str) -> bool:
        """
        Process a single character of input.
        
        This method is implemented for compatibility with CharacterHandler,
        but it should not be used in LineHandler. Instead, use process_line.
        
        Args:
            char: The character to process
            
        Returns:
            True to continue processing, False to terminate the connection
            
        Raises:
            NotImplementedError: Always, as this method should not be used
        """
        raise NotImplementedError(
            "LineHandler does not implement character-by-character processing. "
            "Use process_line instead."
        )