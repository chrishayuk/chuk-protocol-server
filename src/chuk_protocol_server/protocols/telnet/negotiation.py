#!/usr/bin/env python3
# chuk_protocol_server/protocols/telnet/negotation.py
"""
Telnet Negotiation Module

This module provides functions for telnet option negotiation,
handling the details of sending and interpreting telnet commands.
"""

import asyncio
import logging
from typing import Optional, Tuple

from chuk_protocol_server.protocols.telnet.constants import (
    IAC, DO, DONT, WILL, WONT, SB, SE,
    OPT_ECHO, OPT_SGA, OPT_TERMINAL, OPT_NAWS, OPT_LINEMODE,
    TERMINAL_SEND, get_command_name, get_option_name
)

# logger
logger = logging.getLogger('chuk-protocol-server')

async def _async_write(writer: asyncio.StreamWriter, data: bytes) -> None:
    """
    Write data to the writer and await if needed.
    
    This helper function calls the writer's write method and checks if it returns
    a coroutine. It also drains the writer, awaiting any coroutines as needed.
    
    Args:
        writer: The stream writer to send data to.
        data: The data to send.
    """
    result = writer.write(data)
    if asyncio.iscoroutine(result):
        await result
    drain = getattr(writer, "drain", None)
    if drain is not None:
        drain_result = drain()
        if asyncio.iscoroutine(drain_result):
            await drain_result

async def send_command(writer: asyncio.StreamWriter, command: int, option: int) -> None:
    """
    Send a telnet command with the given option.
    
    Args:
        writer: The stream writer to send the command to.
        command: The telnet command (DO, DONT, WILL, WONT).
        option: The option code.
    """
    logger.debug(f"Sending {get_command_name(command)} {get_option_name(option)}")
    await _async_write(writer, bytes([IAC, command, option]))

async def send_subnegotiation(writer: asyncio.StreamWriter, option: int, data: bytes) -> None:
    """
    Send a telnet subnegotiation with the given option and data.
    
    Args:
        writer: The stream writer to send the subnegotiation to.
        option: The option code.
        data: The data to include in the subnegotiation.
    """
    subneg = bytearray([IAC, SB, option])
    subneg.extend(data)
    subneg.extend([IAC, SE])
    
    logger.debug(f"Sending subnegotiation for {get_option_name(option)}: {data!r}")
    await _async_write(writer, subneg)

async def request_terminal_type(writer: asyncio.StreamWriter) -> None:
    """
    Request the terminal type from the client.
    
    Args:
        writer: The stream writer to send the request to.
    """
    logger.debug("Requesting terminal type")
    await send_subnegotiation(writer, OPT_TERMINAL, bytes([TERMINAL_SEND]))

async def send_initial_negotiations(writer: asyncio.StreamWriter) -> None:
    """
    Send the standard set of initial telnet negotiations.
    
    This sets up a modern telnet connection with proper terminal handling.
    
    Args:
        writer: The stream writer to send the negotiations to.
    """
    logger.debug("Sending initial negotiations")
    
    # We want to handle echoing ourselves - this server always echoes characters
    # so we consistently inform the client about this behavior.
    await send_command(writer, WILL, OPT_ECHO)
    
    # We'll suppress GA (modern telnet behavior).
    await send_command(writer, WILL, OPT_SGA)
    
    # Ask the client to suppress GA as well.
    await send_command(writer, DO, OPT_SGA)
    
    # Request terminal type information.
    await send_command(writer, DO, OPT_TERMINAL)
    
    # Request window size information.
    await send_command(writer, DO, OPT_NAWS)
    
    # We prefer character mode over line mode.
    await send_command(writer, WONT, OPT_LINEMODE)
    
    logger.debug("Initial negotiations sent")

def parse_negotiation(buffer: bytes) -> Tuple[Optional[int], Optional[int], int]:
    """
    Parse a telnet negotiation command from a buffer.
    
    Args:
        buffer: The buffer to parse from.
        
    Returns:
        A tuple of (command, option, consumed_bytes) or (None, None, consumed_bytes)
        if no complete negotiation was found.
    """
    if len(buffer) < 3 or buffer[0] != IAC:
        return None, None, 0
    
    command = buffer[1]
    
    # Check if this is a valid command that takes an option.
    if command in (DO, DONT, WILL, WONT):
        option = buffer[2]
        return command, option, 3
    
    # Either an invalid command or one we don't handle.
    return None, None, 1  # Just consume the IAC

def parse_subnegotiation(buffer: bytes) -> Tuple[Optional[int], Optional[bytes], int]:
    """
    Parse a telnet subnegotiation from a buffer.
    
    Args:
        buffer: The buffer to parse from.
        
    Returns:
        A tuple of (option, data, consumed_bytes) or (None, None, consumed_bytes)
        if no complete subnegotiation was found.
    """
    if len(buffer) < 4 or buffer[0] != IAC or buffer[1] != SB:
        return None, None, 0
    
    # Look for IAC SE to end the subnegotiation.
    option = buffer[2]
    
    for i in range(3, len(buffer) - 1):
        if buffer[i] == IAC and buffer[i+1] == SE:
            data = buffer[3:i]
            return option, data, i + 2
    
    # Incomplete subnegotiation.
    return None, None, 0
    
async def process_negotiation(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    command: int,
    option: int,
    option_manager
) -> None:
    """
    Process a telnet negotiation command and update option state.
    
    Args:
        reader: The stream reader.
        writer: The stream writer.
        command: The telnet command.
        option: The option code.
        option_manager: The OptionManager to update.
    """
    logger.debug(f"Processing {get_command_name(command)} {get_option_name(option)}")
    
    if option == OPT_LINEMODE:
        if command == DO:
            logger.debug("Client requests DO LINEMODE => respond WILL LINEMODE")
            await send_command(writer, WILL, OPT_LINEMODE)
            option_manager.set_local_option(OPT_LINEMODE, True)
        elif command == WILL:
            logger.debug("Client says WILL LINEMODE => respond DO LINEMODE")
            await send_command(writer, DO, OPT_LINEMODE)
            option_manager.set_remote_option(OPT_LINEMODE, True)
        elif command == DONT:
            logger.debug("Client says DONT LINEMODE => stay in char mode")
            option_manager.set_local_option(OPT_LINEMODE, False)
        elif command == WONT:
            logger.debug("Client says WONT LINEMODE => stay in char mode")
            option_manager.set_remote_option(OPT_LINEMODE, False)
    
    elif option == OPT_ECHO:
        if command == DO:
            logger.debug("Client says DO ECHO - we agree")
            await send_command(writer, WILL, OPT_ECHO)
            option_manager.set_local_option(OPT_ECHO, True)
        elif command == DONT:
            logger.debug("Client says DONT ECHO - but we need to handle echo")
            option_manager.set_local_option(OPT_ECHO, True)
        elif command == WILL:
            logger.debug("Client says WILL ECHO - we refuse")
            await send_command(writer, DONT, OPT_ECHO)
            option_manager.set_remote_option(OPT_ECHO, False)
        elif command == WONT:
            logger.debug("Client says WONT ECHO - that's fine")
            option_manager.set_remote_option(OPT_ECHO, False)
    
    elif option == OPT_SGA:
        if command == DO:
            logger.debug("Client says DO SGA - we agree")
            await send_command(writer, WILL, OPT_SGA)
            option_manager.set_local_option(OPT_SGA, True)
        elif command == WILL:
            logger.debug("Client says WILL SGA - good")
            option_manager.set_remote_option(OPT_SGA, True)
    
    elif option == OPT_TERMINAL:
        if command == WILL:
            logger.debug("Client says WILL TERMINAL - requesting type")
            option_manager.set_remote_option(OPT_TERMINAL, True)
            await request_terminal_type(writer)
    
    elif option == OPT_NAWS:
        if command == WILL:
            logger.debug("Client says WILL NAWS - good")
            option_manager.set_remote_option(OPT_NAWS, True)
    
    else:
        logger.debug(f"Refusing unknown option: {get_option_name(option)}")
        if command == DO:
            await send_command(writer, WONT, option)
        elif command == WILL:
            await send_command(writer, DONT, option)
