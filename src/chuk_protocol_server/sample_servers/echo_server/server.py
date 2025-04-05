#!/usr/bin/env python3
# sample_servers/echo_sercer/echo_server.py
"""
Echo Telnet Server Implementation

A simple telnet server that echoes back what you type.
This example demonstrates how to create a custom telnet handler
using the modular telnet server framework.
"""
import asyncio
import logging
from typing import Optional

# Update import paths to match your directory structure
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler
from chuk_protocol_server.servers.telnet_server import TelnetServer

# Configure logging for this module
logger = logging.getLogger('echo-telnet-server')

class EchoTelnetHandler(TelnetHandler):
    """
    Custom telnet handler that echoes back commands.
    
    This class demonstrates how to create a simple custom handler
    by overriding the on_command_submitted method.
    """
    
    async def on_command_submitted(self, command: str) -> None:
        """
        Process a command by echoing it back to the user.
        
        Args:
            command: The command submitted by the user
        """
        logger.info(f"Received command from {self.addr}: {command}")
        
        # Process special commands
        if command.lower() == 'help':
            await self.show_help()
        elif command.lower() == 'info':
            await self.show_info()
        else:
            # Echo back the command
            await self.send_line(f"Echo: {command}")
    
    async def show_help(self) -> None:
        """
        Show help information to the user.
        """
        help_text = [
            "Echo Server Help",
            "----------------",
            "Available commands:",
            "  help  - Show this help message",
            "  info  - Show connection information",
            "  quit  - Disconnect from the server",
            "",
            "Any other input will be echoed back to you."
        ]
        
        for line in help_text:
            await self.send_line(line)
    
    async def show_info(self) -> None:
        """
        Show connection information to the user.
        """
        # Build info text with basic connection details
        # Note: We're using properties available in all TelnetHandlers
        info_text = [
            "Connection Information",
            "---------------------",
            f"Connected from: {self.addr}",
            f"Line mode: {'Enabled' if self.line_mode else 'Disabled'}",
        ]
        
        # Add terminal info if available
        if hasattr(self, 'terminal'):
            try:
                info_text.append(f"Terminal type: {self.terminal.term_type}")
                info_text.append(f"Window size: {self.terminal.window_size[0]}x{self.terminal.window_size[1]}")
            except AttributeError:
                info_text.append("Terminal information not available")
        
        # Add option info if available
        if hasattr(self, 'options'):
            try:
                info_text.append(f"Echo option: {'Enabled' if self.options.is_local_enabled(1) else 'Disabled'}")
            except AttributeError:
                info_text.append("Option information not available")
        
        for line in info_text:
            await self.send_line(line)
    
    async def send_welcome(self) -> None:
        """
        Send a welcome message to the client.
        """
        # Check if a custom welcome message was specified in server config
        custom_welcome = None
        if hasattr(self.server, 'welcome_message'):
            custom_welcome = self.server.welcome_message
        
        # Default welcome message
        welcome_text = [
            custom_welcome or "Welcome to the Echo Server!",
            "-------------------------",
            "Type 'help' for available commands.",
            "Type 'quit' to disconnect."
        ]
        
        for line in welcome_text:
            await self.send_line(line)
        
        await self.show_prompt()

    async def process_line(self, line: str) -> bool:
        """
        Override process_line for consistent behavior across all transport modes.
        
        This ensures that the echo server works the same way in both telnet and websocket modes.
        
        Args:
            line: The line to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        logger.debug(f"EchoTelnetHandler process_line => {line!r}")
        
        # Check for exit commands first
        if line.lower() in ['quit', 'exit', 'q']:
            await self.send_line("Goodbye!")
            await self.end_session()
            return False
        
        # Process the command through on_command_submitted
        await self.on_command_submitted(line)
        
        # Continue processing
        return True

# Standalone server functionality if this module is executed directly
async def main():
    """
    Main function to start the echo server.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Server parameters
    host, port = '0.0.0.0', 8023
    
    # Create and start the server
    logger.info(f"Starting Echo Server on {host}:{port}")
    server = TelnetServer(host, port, EchoTelnetHandler)
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown initiated by user.")
    except Exception as e:
        logger.error(f"Error running server: {e}")
    finally:
        logger.info("Echo Server has shut down.")

# Run the server if this module is executed directly
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")