#!/usr/bin/env python3
# chuk_protocol_server/protocols/telnet/options.py
"""
Telnet Options Manager

This module provides classes for managing telnet options state,
tracking which options are enabled on both the local and remote sides.
"""
import logging
from typing import Dict, Set, Optional

# imports
from chuk_protocol_server.protocols.telnet.constants import get_option_name

# logger
logger = logging.getLogger('chuk-protocol-server')

class OptionManager:
    """
    Manages the state of telnet options for both local and remote sides.
    
    This class tracks which options are enabled or disabled, provides methods
    to update option states, and helps enforce proper telnet option negotiation.
    """
    
    def __init__(self):
        """
        Initialize the option manager with empty option dictionaries.
        
        By default, all options are disabled until explicitly enabled
        through negotiation.
        """
        # Options we (server) have enabled
        self.local_options: Dict[int, bool] = {}
        
        # Options the client has enabled
        self.remote_options: Dict[int, bool] = {}
        
        # Options we're in the process of negotiating
        self._pending_local: Set[int] = set()
        self._pending_remote: Set[int] = set()
    
    def initialize_options(self, options):
        """
        Initialize the state for a set of options.
        
        Args:
            options: A list of option codes to initialize
        """
        for opt in options:
            self.local_options[opt] = False
            self.remote_options[opt] = False
    
    def set_local_option(self, option: int, enabled: bool):
        """
        Set the state of a local option.
        
        Args:
            option: The option code
            enabled: Whether the option should be enabled
        """
        self.local_options[option] = enabled
        
        # Remove from pending if we've set its state
        if option in self._pending_local:
            self._pending_local.remove(option)
        
        logger.debug(f"Local option {get_option_name(option)} {'enabled' if enabled else 'disabled'}")
    
    def set_remote_option(self, option: int, enabled: bool):
        """
        Set the state of a remote option.
        
        Args:
            option: The option code
            enabled: Whether the option should be enabled
        """
        self.remote_options[option] = enabled
        
        # Remove from pending if we've set its state
        if option in self._pending_remote:
            self._pending_remote.remove(option)
            
        logger.debug(f"Remote option {get_option_name(option)} {'enabled' if enabled else 'disabled'}")
    
    def mark_pending_local(self, option: int):
        """
        Mark a local option as pending negotiation.
        
        Args:
            option: The option code
        """
        self._pending_local.add(option)
    
    def mark_pending_remote(self, option: int):
        """
        Mark a remote option as pending negotiation.
        
        Args:
            option: The option code
        """
        self._pending_remote.add(option)
    
    def is_local_enabled(self, option: int) -> bool:
        """
        Check if a local option is enabled.
        
        Args:
            option: The option code
            
        Returns:
            True if the option is enabled, False otherwise
        """
        return self.local_options.get(option, False)
    
    def is_remote_enabled(self, option: int) -> bool:
        """
        Check if a remote option is enabled.
        
        Args:
            option: The option code
            
        Returns:
            True if the option is enabled, False otherwise
        """
        return self.remote_options.get(option, False)
    
    def is_local_pending(self, option: int) -> bool:
        """
        Check if a local option is pending negotiation.
        
        Args:
            option: The option code
            
        Returns:
            True if the option is pending, False otherwise
        """
        return option in self._pending_local
    
    def is_remote_pending(self, option: int) -> bool:
        """
        Check if a remote option is pending negotiation.
        
        Args:
            option: The option code
            
        Returns:
            True if the option is pending, False otherwise
        """
        return option in self._pending_remote
    
    def get_option_status(self, option: int) -> str:
        """
        Get a human-readable status string for an option.
        
        Args:
            option: The option code
            
        Returns:
            A string describing the current option state
        """
        option_name = get_option_name(option)
        local_state = "enabled" if self.is_local_enabled(option) else "disabled"
        remote_state = "enabled" if self.is_remote_enabled(option) else "disabled"
        
        return f"{option_name}: local={local_state}, remote={remote_state}"
    
    def __repr__(self) -> str:
        """Return a string representation of the option manager."""
        return f"OptionManager(local={self.local_options}, remote={self.remote_options})"