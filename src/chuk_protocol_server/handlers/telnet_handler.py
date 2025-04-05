#!/usr/bin/env python3
# chuk_protocol_server/handlers/telnet_handler.py
"""
Telnet Protocol Handler

This module provides a handler for the Telnet protocol, which combines
the character and line handlers with telnet-specific protocol handling.
If self.mode == "simple", it bypasses Telnet negotiation and uses a plain
line-based loop, similar to a TCP fallback.
"""

import asyncio
import logging
from typing import Optional

# Base line handler
from chuk_protocol_server.handlers.line_handler import LineHandler

# Telnet constants and utilities
from chuk_protocol_server.protocols.telnet.constants import (
    IAC, DO, DONT, WILL, WONT, SB, SE,
    OPT_ECHO, OPT_SGA, OPT_TERMINAL, OPT_NAWS, OPT_LINEMODE
)
from chuk_protocol_server.protocols.telnet.negotiation import (
    send_initial_negotiations, process_negotiation
)
from chuk_protocol_server.protocols.telnet.options import OptionManager
from chuk_protocol_server.protocols.telnet.terminal import TerminalInfo
from chuk_protocol_server.utils.terminal_codes import CR, LF

# logger
logger = logging.getLogger('chuk-protocol-server')

class TelnetHandler(LineHandler):
    """
    Telnet protocol handler that can also operate in a "simple" (line-based, no negotiation) mode.
    
    If self.mode == "simple", it reads lines directly and echoes them
    without sending or parsing Telnet negotiation sequences. Otherwise,
    it does normal Telnet negotiation and can handle line or character mode.
    """
    
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        super().__init__(reader, writer)

        self.line_mode = False  # If Telnet negotiation sets linemode
        self.options = OptionManager()
        self.options.initialize_options([
            OPT_ECHO, OPT_SGA, OPT_TERMINAL, OPT_NAWS, OPT_LINEMODE
        ])
        self.terminal = TerminalInfo()
        
        # Buffer for partial IAC commands
        self.iac_buffer = bytearray()
        
        # Custom welcome message that can be set by server configuration
        self.welcome_message = None
    
    async def handle_client(self) -> None:
        """
        Main entry point. Checks if self.mode == "simple". If so, uses a purely
        line-based loop with no negotiation. Otherwise, does full Telnet logic.
        """
        try:
            await self.on_connect()
            
            if getattr(self, 'mode', 'telnet') == "simple":
                logger.debug("TelnetHandler: skipping Telnet negotiation (simple mode).")
                await self.send_welcome()
                await self._simple_line_loop()  # read lines with no expansions
            else:
                logger.debug("TelnetHandler: performing Telnet negotiation.")
                await self._send_initial_negotiations()
                await self.send_welcome()
                await self._telnet_loop()
        finally:
            await self.on_disconnect()
            await self.cleanup()
    
    async def _send_initial_negotiations(self) -> None:
        """Send typical Telnet negotiations (WILL ECHO, DO SGA, etc.)."""
        await send_initial_negotiations(self.writer)

    async def _simple_line_loop(self) -> None:
        """
        A purely line-based loop, ignoring Telnet commands,
        used when self.mode == "simple".
        """
        while self.running:
            line_bytes = await self.reader.readline()
            if not line_bytes:
                logger.debug(f"Client {self.addr} disconnected (simple mode).")
                break
            
            line_str = line_bytes.decode('utf-8', errors='ignore').rstrip('\r\n')
            logger.debug(f"(simple_line_loop) => {line_str!r}")
            
            cont = await self.process_line(line_str)
            if not cont:
                break

    async def _telnet_loop(self) -> None:
        """
        Normal Telnet logic. If line_mode is True, read lines with
        _read_line_with_telnet(). Otherwise, read chars with _read_mixed_mode().
        """
        while self.running:
            try:
                if self.line_mode:
                    line = await self._read_line_with_telnet()
                    if not line:
                        logger.debug(f"Client {self.addr} disconnected (Telnet line mode).")
                        break
                    cont = await self.process_line(line)
                    if not cont:
                        break
                else:
                    data = await self._read_mixed_mode()
                    if data is None:
                        logger.debug(f"Client {self.addr} disconnected (Telnet char mode).")
                        break
                    if data:
                        for char in data:
                            cont = await self.default_process_character(char)
                            if not cont:
                                break
                        else:
                            continue
                        break
            except asyncio.CancelledError:
                logger.debug(f"Telnet loop cancelled for {self.addr}.")
                break
            except Exception as e:
                await self.on_error(e)
                if "Connection reset" in str(e) or "Broken pipe" in str(e):
                    break
                await asyncio.sleep(1)

    async def _read_mixed_mode(self, timeout: float = 300) -> Optional[str]:
        """
        Read both Telnet commands and data interleaved. This is used if
        line_mode is False and we're in normal Telnet mode (not 'simple').
        """
        try:
            raw_data = await asyncio.wait_for(self.reader.read(1024), timeout=timeout)
            if not raw_data:
                return None
            logger.debug(f"Raw data received: {[b for b in raw_data]}")
            
            processed_chars = ""
            i = 0
            while i < len(raw_data):
                byte = raw_data[i]
                if byte == IAC:
                    i = await self._handle_iac(raw_data, i)
                else:
                    i, processed_chars = self._handle_regular_char(raw_data, i, processed_chars)
            logger.debug(f"Processed data: {processed_chars!r}")
            return processed_chars
        except asyncio.TimeoutError:
            return ""
        except Exception as e:
            logger.error(f"Error in _read_mixed_mode: {e}")
            return None

    async def _handle_iac(self, raw_data: bytes, i: int) -> int:
        """Handle an IAC (Telnet command) in the raw_data buffer."""
        i += 1
        if i >= len(raw_data):
            self.iac_buffer.append(IAC)
            return i
        cmd = raw_data[i]
        if cmd in (DO, DONT, WILL, WONT):
            i = await self._process_do_dont_will_wont(raw_data, i, cmd)
        elif cmd == SB:
            i = self._process_subneg(raw_data, i)
        elif cmd == IAC:
            # IAC IAC means literal 255
            # We'll just skip it here and add a 255 to the processed chars if you want
            pass
        return i + 1

    async def _process_do_dont_will_wont(self, raw_data: bytes, i: int, cmd: int) -> int:
        i += 1
        if i < len(raw_data):
            option = raw_data[i]
            from chuk_protocol_server.protocols.telnet.negotiation import process_negotiation
            await process_negotiation(self.reader, self.writer, cmd, option, self.options)
            if option == OPT_LINEMODE:
                self.line_mode = (
                    self.options.is_local_enabled(OPT_LINEMODE) or
                    self.options.is_remote_enabled(OPT_LINEMODE)
                )
        else:
            self.iac_buffer.extend([IAC, cmd])
        return i

    def _process_subneg(self, raw_data: bytes, i: int) -> int:
        """Read until IAC SE for subnegotiation."""
        i += 1
        sub_data = bytearray()
        found_se = False
        while i < len(raw_data) - 1:
            if raw_data[i] == IAC and raw_data[i+1] == SE:
                i += 1
                found_se = True
                break
            sub_data.append(raw_data[i])
            i += 1
        if found_se:
            self._process_subnegotiation(sub_data)
        else:
            self.iac_buffer.extend([IAC, SB])
            self.iac_buffer.extend(sub_data)
        return i

    def _handle_regular_char(self, raw_data: bytes, i: int, out: str) -> (int, str):
        """Handle a regular character (including CR LF combos)."""
        byte = raw_data[i]
        if byte == CR:
            if i + 1 < len(raw_data):
                next_byte = raw_data[i+1]
                if next_byte == LF:
                    out += "\n"
                    return i + 2, out
                elif next_byte == 0:
                    out += "\r"
                    return i + 2, out
            out += "\r"
            return i + 1, out
        
        # Add printable or recognized control chars
        if (32 <= byte <= 126) or byte in (8, 10, 13, 3, 127):
            out += chr(byte)
        return i + 1, out

    def _process_subnegotiation(self, data: bytearray) -> None:
        """Handle subneg data for TERMINAL-TYPE, NAWS, etc."""
        logger.debug(f"Processing subnegotiation data: {list(data)}")
        if not data:
            return
        option = data[0]
        if option == OPT_TERMINAL and len(data) > 1:
            if data[1] == 0:  # IS
                self.terminal.process_terminal_type_data(data[1:])
        elif option == OPT_NAWS and len(data) >= 5:
            self.terminal.process_window_size_data(data[1:])

    async def _read_line_with_telnet(self, timeout: float = 300) -> Optional[str]:
        """
        In line mode, read a line but skip Telnet sequences. 
        """
        try:
            data = await asyncio.wait_for(self.reader.readline(), timeout=timeout)
            if not data:
                return None
            line_bytes = bytearray()
            i = 0
            while i < len(data):
                if data[i] == IAC:
                    i += 1
                    if i < len(data):
                        # Could handle DO, DONT, etc. or skip them
                        if data[i] == IAC:  # literal 255
                            line_bytes.append(IAC)
                        else:
                            # skip option byte
                            i += 1
                    i += 1
                    continue
                if data[i] in (CR, LF) and i >= len(data) - 2:
                    i += 1
                    continue
                line_bytes.append(data[i])
                i += 1
            line_str = line_bytes.decode('utf-8', errors='ignore')
            logger.debug(f"Line-mode read => {line_str!r}")
            return line_str
        except asyncio.TimeoutError:
            logger.debug("Timeout reading line in Telnet line mode")
            return None
        except Exception as e:
            logger.error(f"Error in _read_line_with_telnet: {e}")
            return None
    
    async def send_welcome(self) -> None:
        """
        Send a welcome message to the client.
        
        Uses the custom welcome_message if set, otherwise sends a default message.
        """
        if self.welcome_message:
            await self.send_line(self.welcome_message)
        else:
            await self.send_line("Welcome! This server can handle line or character mode.")
        
        await self.show_prompt()

    async def process_line(self, line: str) -> bool:
        """
        Process a complete line of input.
        
        Args:
            line: The line to process
            
        Returns:
            True to continue processing, False to terminate the connection
        """
        logger.debug(f"process_line => {line!r}")
        if line.lower() in ['quit', 'exit', 'q']:
            await self.end_session("Goodbye!")
            return False
        await self.send_line(f"Echo: {line}")
        return True