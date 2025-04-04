#!/usr/bin/env python3
# chuk_protocol_server/protocols/telnet/constants.py
"""
Telnet Protocol Constants

This module defines constants used in the telnet protocol, centralizing
all numeric values to improve code readability and maintainability.
"""

# Telnet command codes
IAC  = 255  # Interpret As Command
DONT = 254
DO   = 253
WONT = 252
WILL = 251
SB   = 250  # Subnegotiation Begin
SE   = 240  # Subnegotiation End

# Telnet control codes
NUL = 0     # NULL
LF  = 10    # Line Feed
CR  = 13    # Carriage Return
BS  = 8     # Backspace
DEL = 127   # Delete
CTRL_C = 3  # Ctrl+C

# Telnet option codes
OPT_ECHO = 1        # Echo
OPT_SGA = 3         # Suppress Go Ahead
OPT_STATUS = 5      # Status
OPT_TIMING = 6      # Timing Mark
OPT_TERMINAL = 24   # Terminal Type
OPT_NAWS = 31       # Window Size
OPT_TSPEED = 32     # Terminal Speed
OPT_LINEMODE = 34   # Line Mode
OPT_ENVIRON = 36    # Environment Variables
OPT_NEW_ENVIRON = 39  # New Environment Variables

# Terminal type query
TERMINAL_SEND = 1   # Send terminal type
TERMINAL_IS = 0     # Terminal type is

# Option descriptions for logging
OPTION_NAMES = {
    OPT_ECHO: "ECHO",
    OPT_SGA: "SGA",
    OPT_STATUS: "STATUS",
    OPT_TIMING: "TIMING-MARK",
    OPT_TERMINAL: "TERMINAL-TYPE",
    OPT_NAWS: "NAWS",
    OPT_TSPEED: "TERMINAL-SPEED",
    OPT_LINEMODE: "LINEMODE",
    OPT_ENVIRON: "ENVIRON",
    OPT_NEW_ENVIRON: "NEW-ENVIRON"
}

# Command descriptions for logging
COMMAND_NAMES = {
    DO: "DO",
    DONT: "DONT",
    WILL: "WILL",
    WONT: "WONT",
    SB: "SB",
    SE: "SE"
}

def get_option_name(option):
    """Return a human-readable name for an option code."""
    return OPTION_NAMES.get(option, f"UNKNOWN-OPTION-{option}")

def get_command_name(command):
    """Return a human-readable name for a command code."""
    return COMMAND_NAMES.get(command, f"UNKNOWN-COMMAND-{command}")