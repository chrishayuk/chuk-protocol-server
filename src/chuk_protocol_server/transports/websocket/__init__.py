"""
WebSocket Transport Package

This package provides a WebSocket transport implementation for
the telnet server framework, allowing browsers to connect directly
without requiring a proxy.
"""

# Check if websockets package is available
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Re-export classes for convenience if websockets is available
if WEBSOCKETS_AVAILABLE:
    try:
        from chuk_protocol_server.transports.websocket.ws_adapter import WebSocketAdapter
        from chuk_protocol_server.transports.websocket.ws_reader import WebSocketReader
        from chuk_protocol_server.transports.websocket.ws_writer import WebSocketWriter
        
        __all__ = [
            'WebSocketAdapter',
            'WebSocketReader',
            'WebSocketWriter',
            'WEBSOCKETS_AVAILABLE'
        ]
    except ImportError:
        # If something else fails, just export the availability flag
        __all__ = ['WEBSOCKETS_AVAILABLE']
else:
    __all__ = ['WEBSOCKETS_AVAILABLE']