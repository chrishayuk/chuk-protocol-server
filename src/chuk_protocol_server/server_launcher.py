#!/usr/bin/env python3
# chuk_protocol_server/server_launcher.py
"""
Universal Server Launcher

This module provides a flexible, configuration-driven approach to launching 
servers with different transport protocols. It supports dynamic handler loading,
YAML configuration parsing, and launching multiple servers concurrently.

Features:
- Single Ctrl-C triggers graceful shutdown of each server.
- Configuration from YAML or command-line arguments.
- Supports multiple server entries in one config file.
"""

import asyncio
import argparse
import importlib
import logging
import signal
import sys
import os
from typing import Type, Dict, Any, Union, List

from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_server import BaseServer

# Define transport constants
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket"
TCP_TRANSPORT = "tcp"
WS_TELNET_TRANSPORT = "ws_telnet"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TCP_TRANSPORT, TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]

def setup_logging(verbosity: int = 1) -> None:
    """
    Configure logging level and format based on verbosity.
    """
    log_levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = log_levels.get(verbosity, logging.DEBUG)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def load_handler_class(handler_path: str) -> Type[BaseHandler]:
    """
    Dynamically load a handler class from a string path: 'module.submodule:ClassName'.
    """
    try:
        module_path, class_name = handler_path.split(':')
        module = importlib.import_module(module_path)
        handler_class = getattr(module, class_name)
        if not issubclass(handler_class, BaseHandler):
            raise TypeError(f"{class_name} must be a subclass of BaseHandler")
        return handler_class
    except (ValueError, ImportError, AttributeError) as e:
        raise ValueError(f"Could not load handler class '{handler_path}': {e}")

def create_server_instance(handler_class: Type[BaseHandler], config: Dict[str, Any]) -> BaseServer:
    """
    Create a server instance from a configuration dictionary and a handler class.
    """
    from chuk_protocol_server.server_config import ServerConfig
    return ServerConfig.create_server_from_config(config, handler_class)

async def run_server(server: BaseServer) -> None:
    """
    Start an individual server's main loop.
    """
    try:
        await server.start_server()
    except Exception as e:
        logging.error(f"Error running server {server.__class__.__name__}: {e}")

async def run_multiple_servers(servers: List[BaseServer]) -> None:
    """
    Run multiple servers concurrently with coordinated shutdown.
    """
    tasks = [asyncio.create_task(run_server(server)) for server in servers]
    
    try:
        # Wait for all servers to complete (or be cancelled)
        await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        # Handle task cancellation by shutting down all servers
        logging.info("Server tasks are being cancelled")
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

async def shutdown_all_servers(servers: List[BaseServer]) -> None:
    """
    Gracefully shut down all servers in sequence.
    """
    logging.info("Shutting down all servers...")
    
    for server in servers:
        try:
            await server.shutdown()
        except Exception as e:
            logging.error(f"Error shutting down {server.__class__.__name__}: {e}")
    
    logging.info("All servers have shut down.")

def setup_signal_handlers(loop: asyncio.AbstractEventLoop, servers: List[BaseServer]) -> None:
    """
    Set up signal handlers for graceful shutdown across all servers.
    """
    shutdown_task = None
    
    def shutdown_handler():
        nonlocal shutdown_task
        
        # Prevent multiple shutdown attempts
        if shutdown_task is not None and not shutdown_task.done():
            logging.info("Shutdown already in progress")
            return
        
        logging.info("Received shutdown signal")
        shutdown_task = asyncio.create_task(shutdown_all_servers(servers))
    
    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)
    
    logging.info("Signal handlers registered for graceful shutdown")

async def async_main(args: argparse.Namespace) -> int:
    """
    Asynchronous main function to set up and run servers.
    """
    server_configs = []
    
    try:
        # If config file provided:
        if args.config:
            from chuk_protocol_server.server_config import ServerConfig
            config = ServerConfig.load_config(args.config)
            logging.info(f"Loaded configuration from {args.config}")
            
            if "servers" in config:
                # Multi-server config
                for server_name, server_conf in config["servers"].items():
                    logging.info(f"Configuring server: {server_name}")
                    handler_class = load_handler_class(server_conf['handler_class'])
                    
                    # Apply CLI overrides if present
                    if args.host != '0.0.0.0':
                        server_conf['host'] = args.host
                    if args.port != 8023:
                        server_conf['port'] = args.port
                    if args.transport != TRANSPORT_TELNET:
                        server_conf['transport'] = args.transport
                    
                    # Validate, create, store
                    ServerConfig.validate_config(server_conf)
                    server_instance = create_server_instance(handler_class, server_conf)
                    server_configs.append(server_instance)
            else:
                # Single-server config
                handler_class = load_handler_class(config['handler_class'])
                
                if args.host != '0.0.0.0':
                    config['host'] = args.host
                if args.port != 8023:
                    config['port'] = args.port
                if args.transport != TRANSPORT_TELNET:
                    config['transport'] = args.transport
                
                ServerConfig.validate_config(config)
                server_configs.append(create_server_instance(handler_class, config))
        
        else:
            # No config file, direct CLI
            handler_class = load_handler_class(args.handler)
            config = {
                'host': args.host,
                'port': args.port,
                'transport': args.transport
            }
            server_configs.append(create_server_instance(handler_class, config))
        
        # Log servers to be launched
        for server in server_configs:
            transport_name = getattr(server, 'transport', TRANSPORT_TELNET).upper()
            logging.info(
                f"Starting {transport_name} server with {server.handler_class.__name__} "
                f"on {server.host}:{server.port}"
            )
        
        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        setup_signal_handlers(loop, server_configs)
        
        # Run all servers
        await run_multiple_servers(server_configs)
        
        return 0
    
    except asyncio.CancelledError:
        logging.info("Main task cancelled")
        return 0
    
    except Exception as e:
        logging.error(f"Error in server launcher: {e}")
        if args.verbose >= 2:
            import traceback
            traceback.print_exc()
        return 1

def main():
    parser = argparse.ArgumentParser(
        description='Universal Server Launcher',
        epilog='Launch servers with different transport protocols'
    )
    
    # Handler can come from a direct CLI arg or from a YAML config
    handler_group = parser.add_mutually_exclusive_group(required=True)
    handler_group.add_argument(
        'handler', 
        type=str, 
        nargs='?', 
        default=None,
        help='Handler class path (e.g., "telnet_server.handlers.telnet_handler:TelnetHandler")'
    )
    handler_group.add_argument(
        '--config', '-c', 
        type=str,
        help='Path to YAML configuration file'
    )
    
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8023, help='Port to listen on (default: 8023)')
    parser.add_argument('--transport', type=str, choices=SUPPORTED_TRANSPORTS, default=TRANSPORT_TELNET,
                        help=f'Transport protocol (default: {TRANSPORT_TELNET})')
    parser.add_argument('-v', '--verbose', action='count', default=1, help='Increase verbosity (can be used multiple times)')
    
    args = parser.parse_args()
    setup_logging(args.verbose)
    
    # Run the async main with proper shutdown handling
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        # This should rarely happen due to our signal handlers
        logging.info("Server shutdown initiated via KeyboardInterrupt.")
        return 0
    finally:
        logging.info("Server launcher completed.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())