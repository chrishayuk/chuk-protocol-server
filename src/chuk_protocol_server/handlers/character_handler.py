#!/usr/bin/env python3
# chuk_protocol_server/handlers/character_handler.py
"""
Character Protocol Handler

This module provides a handler for character-by-character input processing,
which is essential for interactive applications like command shells.
"""
import asyncio
import logging
from typing import Optional

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.utils.terminal_codes import CR, LF, CRLF, ERASE_CHAR

# logger
logger = logging.getLogger('chuk-protocol-server')

class CharacterHandler(BaseHandler):
    """
    Handles character-by-character input processing.
    
    This class extends the BaseHandler to provide character-by-character input
    processing, which is useful for interactive applications that need to respond
    to each keystroke, such as command shells or text editors.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the character handler.
        
        Args:
            reader: The stream reader for reading from the client
            writer: The stream writer for writing to the client
        """
        super().__init__(reader, writer)
        self.current_command = ""  # Current command being built
    
    async def handle_client(self) -> None:
        """
        Main client handling loop for character mode.
        
        This method reads characters one by one and processes them
        by calling the process_character method.
        """
        try:
            await self.on_connect()
            
            # Send welcome message
            await self.send_welcome()
            
            # Main processing loop
            while self.running:
                try:
                    # Read a single character
                    char = await self.read_character()
                    
                    # Check if the connection was closed
                    if char is None:
                        logger.debug(f"Client {self.addr} disconnected")
                        break
                    
                    # Process the character
                    should_continue = await self.process_character(char)
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
    
    async def read_character(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Read a single character from the client.
        
        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            The character read, or None if the connection is closed
            
        Raises:
            asyncio.TimeoutError: If the timeout expires
        """
        try:
            # Read a single byte
            data = await self.read_raw(1, timeout)
            
            # Check if the connection was closed
            if not data:
                return None
            
            # Convert to string using 'replace' to substitute invalid UTF-8 bytes
            return data.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            # Fallback: return the Unicode replacement character
            logger.warning(f"Invalid UTF-8 sequence from {self.addr}")
            return "�"  # Unicode replacement character
        except asyncio.TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Error reading character from {self.addr}: {e}")
            return None

    async def process_character(self, char: str) -> bool:
        """
        Process a single character of input.
        
        This is the core method for character-by-character processing.
        Subclasses should override this method to implement specific
        character processing logic.
        
        Args:
            char: The character to process
            
        Returns:
            True to continue processing, False to terminate the connection
            
        Raises:
            NotImplementedError: If not overridden by a subclass
        """
        raise NotImplementedError("Subclasses must implement process_character")
    
    async def send_line(self, message: str) -> None:
        """
        Send a line of text with proper line endings.
        
        Args:
            message: The message to send
        """
        try:
            await self.send_raw(message.encode('utf-8') + CRLF)
        except Exception as e:
            logger.error(f"Error sending line to {self.addr}: {e}")
            raise
    
    async def send_welcome(self) -> None:
        """
        Send a welcome message to the client.
        
        This is a hook method that can be overridden by subclasses to
        send a custom welcome message.
        """
        await self.send_line("Welcome to Character Mode")
        await self.show_prompt()
    
    async def show_prompt(self) -> None:
        """
        Display a command prompt to the client.
        
        This is a hook method that can be overridden by subclasses to
        display a custom prompt.
        """
        await self.send_raw(b"> ")
    
    async def handle_backspace(self) -> None:
        """
        Handle a backspace character.
        
        This method removes the last character from the current command
        and sends the appropriate terminal codes to visually erase it.
        """
        if self.current_command:
            # Remove the last character from the current command
            self.current_command = self.current_command[:-1]
            # Send the appropriate terminal codes to visually erase the character
            await self.send_raw(ERASE_CHAR)
    
    async def handle_enter(self) -> bool:
        """
        Handle an Enter key press.
        
        This method processes the current command and clears the command buffer.
        
        Returns:
            True to continue processing, False to terminate the connection
        """
        # Echo a newline
        await self.send_raw(CRLF)
        
        # Get the current command (trimmed)
        command = self.current_command.strip()
        
        # Clear the command buffer
        self.current_command = ""
        
        # Check for exit commands
        if command.lower() in ["exit", "quit", "q"]:
            await self.end_session("Goodbye!")
            return False
        
        # Process the command if not empty
        if command:
            await self.on_command_submitted(command)
        
        # Show the prompt again
        await self.show_prompt()
        return True
    
    async def on_command_submitted(self, command: str) -> None:
        """
        Process a submitted command.
        
        This is a hook method that can be overridden by subclasses to
        implement specific command processing logic.
        
        Args:
            command: The command to process
        """
        # Default implementation just echoes the command
        await self.send_line(f"You entered: {command}")
    
    def add_to_command(self, char: str) -> None:
        """
        Add a character to the current command.
        
        Args:
            char: The character to add
        """
        self.current_command += char
    
    async def default_process_character(self, char: str) -> bool:
        """
        Default implementation of character processing.
        
        This method provides a basic implementation of character processing
        that can be used by subclasses as a starting point.
        
        Args:
            char: The character to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        # Check for control characters
        if char == "\x03":  # Ctrl+C
            await self.send_line("\n^C - Closing connection.")
            return False
        elif char in ("\r", "\n"):  # Enter
            return await self.handle_enter()
        elif char in ("\b", "\x7f"):  # Backspace or Delete
            await self.handle_backspace()
            return True
        else:
            # Regular character - echo it and add to current command
            try:
                await self.send_raw(char.encode('utf-8'))
                self.add_to_command(char)
            except UnicodeEncodeError:
                logger.warning(f"Could not encode character: {repr(char)}")
            
            return True