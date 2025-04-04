#!/usr/bin/env python3
# chuk_protocol_server/server_config.py
"""
Server Configuration Handler with Monitoring Support

This module provides utilities for loading, validating, and applying 
server configuration from YAML files or dictionaries, including session monitoring options.
"""
import os
import logging
import yaml
from typing import Dict, Any, Type, Optional

# imports
from chuk_protocol_server.handlers.base_handler import BaseHandler

# server imports
from chuk_protocol_server.servers.base_server import BaseServer
from chuk_protocol_server.servers.tcp_server import TCPServer
from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer
from chuk_protocol_server.servers.telnet_server import TelnetServer
from chuk_protocol_server.servers.ws_telnet_server import WSTelnetServer

# logger
logger = logging.getLogger('chuk-protocol-server')

# Define transport constants
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket"
TCP_TRANSPORT = "tcp"
WS_TELNET_TRANSPORT = "ws_telnet"

class ServerConfig:
    """
    Utilities for server configuration management.
    """
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            The loaded configuration as a dictionary
            
        Raises:
            FileNotFoundError: If the configuration file is not found
            Exception: If there's an error parsing the YAML
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            if not config:
                raise ValueError(f"Empty or invalid configuration file: {config_path}")
            
            return config
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
            raise
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> None:
        """
        Validate a server configuration dictionary.
        
        Args:
            config: The configuration dictionary to validate
            
        Raises:
            ValueError: If the configuration is missing required fields
        """
        # Check for required fields
        required_fields = ['transport', 'handler_class']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required configuration field: {field}")
        
        # Validate transport type
        transport = config['transport']
        valid_transports = [TRANSPORT_TELNET, TCP_TRANSPORT, TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]
        if transport not in valid_transports:
            raise ValueError(f"Invalid transport type: {transport}. Must be one of {valid_transports}")
        
        # Validate optional fields based on transport
        if transport in [TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]:
            # WebSocket specific validations
            if config.get('use_ssl', False):
                if 'ssl_cert' not in config or 'ssl_key' not in config:
                    raise ValueError("SSL enabled but missing ssl_cert or ssl_key")
            
            # Monitoring validations
            if config.get('enable_monitoring', False):
                # Optional checks for monitoring configuration
                pass
    
    @staticmethod
    def create_server_from_config(config: Dict[str, Any], handler_class: Type[BaseHandler]) -> BaseServer:
        """
        Create a server instance from a configuration dictionary and a handler class.
        
        Args:
            config: The configuration dictionary
            handler_class: The handler class to use
            
        Returns:
            The created server instance
            
        Raises:
            ValueError: If the transport type is not supported
        """
        transport = config['transport']
        host = config.get('host', '0.0.0.0')
        port = config.get('port', 8023)
        
        if transport == TRANSPORT_TELNET:
            server = TelnetServer(host, port, handler_class)
        elif transport == TCP_TRANSPORT:
            server = TCPServer(host, port, handler_class)
        elif transport == TRANSPORT_WEBSOCKET:
            # Create a plain WebSocket server
            ws_path = config.get('ws_path', '/ws')
            ping_interval = config.get('ping_interval', 30)
            ping_timeout = config.get('ping_timeout', 10)
            allow_origins = config.get('allow_origins', ['*'])
            
            # Check if SSL is enabled
            ssl_cert = None
            ssl_key = None
            if config.get('use_ssl', False):
                ssl_cert = config.get('ssl_cert')
                ssl_key = config.get('ssl_key')
            
            # Check if monitoring is enabled
            enable_monitoring = config.get('enable_monitoring', False)
            monitor_path = config.get('monitor_path', '/monitor')
            
            server = PlainWebSocketServer(
                host=host,
                port=port,
                handler_class=handler_class,
                path=ws_path,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
                allow_origins=allow_origins,
                ssl_cert=ssl_cert,
                ssl_key=ssl_key,
                enable_monitoring=enable_monitoring,
                monitor_path=monitor_path
            )
        elif transport == WS_TELNET_TRANSPORT:
            # Create a WebSocket Telnet server
            ws_path = config.get('ws_path', '/ws_telnet')
            ping_interval = config.get('ping_interval', 30)
            ping_timeout = config.get('ping_timeout', 10)
            allow_origins = config.get('allow_origins', ['*'])
            
            # Check if SSL is enabled
            ssl_cert = None
            ssl_key = None
            if config.get('use_ssl', False):
                ssl_cert = config.get('ssl_cert')
                ssl_key = config.get('ssl_key')
            
            # Check if monitoring is enabled
            enable_monitoring = config.get('enable_monitoring', False)
            monitor_path = config.get('monitor_path', '/monitor')
            
            server = WSTelnetServer(
                host=host,
                port=port,
                handler_class=handler_class,
                path=ws_path,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
                allow_origins=allow_origins,
                ssl_cert=ssl_cert,
                ssl_key=ssl_key,
                enable_monitoring=enable_monitoring,
                monitor_path=monitor_path
            )
        else:
            raise ValueError(f"Unsupported transport type: {transport}")
        
        # Apply any additional server-specific configuration
        for key, value in config.items():
            if key not in ['transport', 'handler_class', 'host', 'port', 
                          'ws_path', 'ping_interval', 'ping_timeout', 
                          'allow_origins', 'use_ssl', 'ssl_cert', 'ssl_key',
                          'enable_monitoring', 'monitor_path']:
                if hasattr(server, key):
                    setattr(server, key, value)
                else:
                    logger.warning(f"Unknown configuration parameter '{key}' for {server.__class__.__name__}")
        
        return server