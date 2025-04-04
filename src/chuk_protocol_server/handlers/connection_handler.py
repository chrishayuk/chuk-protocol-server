#!/usr/bin/env python3
# chuk_protocol_server/protocol_handlers/connection_handler.py
"""
Generic Connection Handler Module
Base class for protocol-agnostic connection handlers
"""
import asyncio
import logging
from typing import Optional, Any

# logger
logger = logging.getLogger('chuk-protocol-server')

class ConnectionHandler:
    """Base class for implementing connection handlers"""
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Initialize with reader/writer streams"""
        self.reader = reader
        self.writer = writer
        self.addr = writer.get_extra_info('peername')
        self.running = True
        self.server = None  # Will be set by the server after creation
    
    async def handle_client(self) -> None:
        """Handle the client connection - override this in subclasses"""
        raise NotImplementedError("Subclasses must implement handle_client")
    
    async def cleanup(self) -> None:
        """Perform cleanup actions - override as needed"""
        pass
    
    async def read_raw(self, n: int = -1, timeout: Optional[float] = None) -> bytes:
        """Read raw bytes with optional timeout"""
        try:
            if timeout is not None:
                return await asyncio.wait_for(self.reader.read(n), timeout=timeout)
            else:
                return await self.reader.read(n)
        except asyncio.TimeoutError:
            raise  # Let the caller handle timeouts
        except Exception as e:
            logger.error(f"Error reading raw data from {self.addr}: {e}")
            return b''
    
    async def write_raw(self, data: bytes) -> None:
        """Write raw bytes to the client"""
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error writing raw data to {self.addr}: {e}")
            raise
    
    def get_extra_info(self, name: str, default: Any = None) -> Any:
        """Get extra connection info from the transport"""
        return self.writer.get_extra_info(name, default)