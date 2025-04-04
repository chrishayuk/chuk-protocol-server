#!/usr/bin/env python3
# chuk_protocol_server/protocols/telnet/terminal.py
"""
Telnet Terminal Information Module

This module provides classes for managing terminal information
such as terminal type and window size. This information is used
to optimize the user interface for different terminal capabilities.
"""
import logging
from typing import Tuple, Dict, List, Optional

# logger
logger = logging.getLogger('chuk-protocol-server')

class TerminalInfo:
    """
    Stores and manages terminal capabilities information.
    
    This class maintains information about the client's terminal,
    including terminal type and window dimensions. This information
    can be used to optimize the user interface for different terminals.
    """
    
    def __init__(self):
        """
        Initialize terminal information with default values.
        
        Default values are conservative and should work with most
        terminals, but they will be updated through negotiation.
        """
        # Terminal type (e.g., "xterm", "vt100", etc.)
        self.term_type = "UNKNOWN"
        
        # Terminal dimensions (width, height in characters)
        self.width = 80
        self.height = 24
        
        # Terminal capabilities
        self.capabilities = {
            'color': False,
            'graphics': False,
            'utf8': False
        }
        
        # Flag to track if we've received terminal information
        self.terminal_info_received = False
    
    def set_terminal_type(self, term_type: str) -> None:
        """
        Set the terminal type and infer capabilities.
        
        Args:
            term_type: The terminal type string from the client
        """
        self.term_type = term_type
        self.terminal_info_received = True
        
        # Infer capabilities from terminal type
        term_lower = term_type.lower()
        
        # Check for color support
        self.capabilities['color'] = (
            'color' in term_lower or
            'xterm' in term_lower or
            '256' in term_lower or
            'ansi' in term_lower
        )
        
        # Check for graphics support
        self.capabilities['graphics'] = (
            'xterm' in term_lower or
            'rxvt' in term_lower
        )
        
        # Check for UTF-8 support (now also considers 'ansi')
        self.capabilities['utf8'] = (
            'utf' in term_lower or
            'unicode' in term_lower or
            'xterm' in term_lower or
            'ansi' in term_lower
        )
        
        logger.debug(f"Terminal type set to {term_type}, capabilities: {self.capabilities}")
    
    def set_window_size(self, width: int, height: int) -> None:
        """
        Set the window size.
        
        Args:
            width: Window width in characters
            height: Window height in characters
        """
        # Sanity check values
        if width < 10:
            width = 80
        if height < 3:
            height = 24
        
        self.width = width
        self.height = height
        logger.debug(f"Window size set to {width}x{height}")
    
    @property
    def window_size(self) -> Tuple[int, int]:
        """
        Get the window size as a tuple.
        
        Returns:
            A tuple of (width, height)
        """
        return (self.width, self.height)
    
    def has_color(self) -> bool:
        """
        Check if the terminal supports color.
        
        Returns:
            True if the terminal supports color, False otherwise
        """
        return self.capabilities.get('color', False)
    
    def has_graphics(self) -> bool:
        """
        Check if the terminal supports graphical characters.
        
        Returns:
            True if the terminal supports graphics, False otherwise
        """
        return self.capabilities.get('graphics', False)
    
    def has_utf8(self) -> bool:
        """
        Check if the terminal supports UTF-8.
        
        Returns:
            True if the terminal supports UTF-8, False otherwise
        """
        return self.capabilities.get('utf8', False)
    
    def get_terminal_summary(self) -> str:
        """
        Get a summary of terminal information.
        
        Returns:
            A string describing the terminal capabilities
        """
        if not self.terminal_info_received:
            return "Terminal information not yet received"
        
        return (
            f"Terminal: {self.term_type}, Size: {self.width}x{self.height}, "
            f"Color: {'Yes' if self.has_color() else 'No'}, "
            f"Graphics: {'Yes' if self.has_graphics() else 'No'}, "
            f"UTF-8: {'Yes' if self.has_utf8() else 'No'}"
        )
    
    def __repr__(self) -> str:
        """
        Return a string representation of the terminal info.
        
        Returns:
            A string representation of the terminal info
        """
        return (
            f"TerminalInfo(type={self.term_type}, size={self.width}x{self.height}, "
            f"capabilities={self.capabilities})"
        )
    
    def process_terminal_type_data(self, data: bytes) -> None:
        """
        Process terminal type subnegotiation data.
        
        Args:
            data: The subnegotiation data
        """
        if not data or data[0] != 0:  # 0 = IS
            logger.warning(f"Invalid terminal type subnegotiation: {data!r}")
            return
        
        try:
            # The terminal type data format is IS <terminal-type>
            term_type = data[1:].decode('ascii', errors='ignore')
            self.set_terminal_type(term_type)
        except Exception as e:
            logger.error(f"Error processing terminal type data: {e}")
    
    def process_window_size_data(self, data: bytes) -> None:
        """
        Process window size subnegotiation data.
        
        Args:
            data: The subnegotiation data
        """
        if len(data) < 4:
            logger.warning(f"Invalid window size subnegotiation: {data!r}")
            return
        
        try:
            # Window size is sent as 2-byte values for width, then height
            width = (data[0] << 8) + data[1]
            height = (data[2] << 8) + data[3]
            self.set_window_size(width, height)
        except Exception as e:
            logger.error(f"Error processing window size data: {e}")
