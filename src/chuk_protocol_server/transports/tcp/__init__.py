"""
Transport Adapters Package

This package provides transport adapters for different protocols,
allowing the same handler classes to work with different transports.
"""

# Define available transports
TRANSPORT_TELNET = "telnet"
TRANSPORT_WEBSOCKET = "websocket"
SUPPORTED_TRANSPORTS = [TRANSPORT_TELNET, TRANSPORT_WEBSOCKET]