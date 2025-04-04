#!/usr/bin/env python3
# chuk_protocol_server/utils/terminal_codes.py
"""
Terminal Control Codes

This module provides constants and functions for terminal control sequences
used to manipulate the terminal display, including cursor movement, colors,
and text formatting.
"""

# Basic control characters
BS = b'\b'           # Backspace
ERASE_CHAR = b'\b \b'  # Sequence to erase a character visually (back, space, back)
CR = b'\r'           # Carriage return
LF = b'\n'           # Line feed
CRLF = b'\r\n'       # Carriage return + line feed
TAB = b'\t'          # Tab
BEL = b'\x07'        # Bell (makes a sound on most terminals)

# ANSI escape sequence introducer
ESC = b'\x1b'        # Escape character
CSI = b'\x1b['       # Control Sequence Introducer (ESC + [)

# ANSI SGR (Select Graphic Rendition) color codes
class Color:
    """ANSI color codes for text styling."""
    # Text colors (foreground)
    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7
    
    # Text formatting
    RESET = 0
    BOLD = 1
    DIM = 2
    ITALIC = 3
    UNDERLINE = 4
    BLINK = 5
    REVERSE = 7
    HIDDEN = 8
    STRIKE = 9

# Terminal control functions
def erase_char() -> bytes:
    """
    Get the sequence to erase the last character.
    
    Returns:
        A byte sequence that erases the last character
    """
    return ERASE_CHAR

def erase_line() -> bytes:
    """
    Get the sequence to erase the current line.
    
    Returns:
        A byte sequence that erases the current line
    """
    return CSI + b'2K' + CR  # Clear entire line and return to start

def erase_screen() -> bytes:
    """
    Get the sequence to erase the entire screen.
    
    Returns:
        A byte sequence that erases the entire screen
    """
    return CSI + b'2J'  # Clear entire screen

def move_cursor(x: int, y: int) -> bytes:
    """
    Get the sequence to move the cursor to a specific position.
    
    Args:
        x: Column position (1-based)
        y: Row position (1-based)
    
    Returns:
        A byte sequence that moves the cursor
    """
    return CSI + f"{y};{x}H".encode()

def move_up(n: int = 1) -> bytes:
    """
    Get the sequence to move the cursor up.
    
    Args:
        n: Number of lines to move up
    
    Returns:
        A byte sequence that moves the cursor up
    """
    return CSI + f"{n}A".encode()

def move_down(n: int = 1) -> bytes:
    """
    Get the sequence to move the cursor down.
    
    Args:
        n: Number of lines to move down
    
    Returns:
        A byte sequence that moves the cursor down
    """
    return CSI + f"{n}B".encode()

def move_right(n: int = 1) -> bytes:
    """
    Get the sequence to move the cursor right.
    
    Args:
        n: Number of columns to move right
    
    Returns:
        A byte sequence that moves the cursor right
    """
    return CSI + f"{n}C".encode()

def move_left(n: int = 1) -> bytes:
    """
    Get the sequence to move the cursor left.
    
    Args:
        n: Number of columns to move left
    
    Returns:
        A byte sequence that moves the cursor left
    """
    return CSI + f"{n}D".encode()

def set_color(fg=None, bg=None, effects=()):
    """
    Get the sequence to set text color and effects.
    
    Args:
        fg: Foreground color code (from Color class)
        bg: Background color code (from Color class)
        effects: Iterable of additional text effects (from Color class)
    
    Returns:
        A byte sequence that sets the color and effects
    """
    attrs = []
    
    # Add effects
    for effect in effects:
        attrs.append(str(effect))
    
    # Add foreground color if specified
    if fg is not None:
        attrs.append(f"3{fg}")
    
    # Add background color if specified
    if bg is not None:
        attrs.append(f"4{bg}")
    
    # If no attributes, just reset
    if not attrs:
        attrs = ["0"]
    
    return CSI + ";".join(attrs).encode() + b'm'

def get_colored_text(text: str, fg=None, bg=None, effects=()):
    """
    Get text with the specified colors and effects applied.
    
    Args:
        text: The text to color
        fg: Foreground color code (from Color class)
        bg: Background color code (from Color class)
        effects: Iterable of additional text effects (from Color class)
    
    Returns:
        Colored text as bytes with automatic reset at the end
    """
    return set_color(fg, bg, effects=effects) + text.encode() + reset_colors()

def reset_colors() -> bytes:
    """
    Get the sequence to reset all text attributes.
    
    Returns:
        A byte sequence that resets colors and effects
    """
    return CSI + b'0m'

def set_title(title: str) -> bytes:
    """
    Get the sequence to set the terminal window title.
    Works in xterm-compatible terminals.
    
    Args:
        title: The title to set
        
    Returns:
        A byte sequence that sets the terminal title
    """
    return ESC + b']0;' + title.encode() + BEL

def hide_cursor() -> bytes:
    """
    Get the sequence to hide the cursor.
    
    Returns:
        A byte sequence that hides the cursor
    """
    return CSI + b'?25l'

def show_cursor() -> bytes:
    """
    Get the sequence to show the cursor.
    
    Returns:
        A byte sequence that shows the cursor
    """
    return CSI + b'?25h'

def save_cursor_position() -> bytes:
    """
    Get the sequence to save the current cursor position.
    
    Returns:
        A byte sequence that saves the cursor position
    """
    return CSI + b's'

def restore_cursor_position() -> bytes:
    """
    Get the sequence to restore the saved cursor position.
    
    Returns:
        A byte sequence that restores the cursor position
    """
    return CSI + b'u'

def create_progress_bar(width: int, progress: float) -> str:
    """
    Create a text-based progress bar.
    
    Args:
        width: Width of the progress bar in characters
        progress: Progress value from 0.0 to 1.0
    
    Returns:
        A string containing the progress bar
    """
    progress = max(0.0, min(1.0, progress))  # Clamp between 0 and 1
    filled = int(width * progress)
    bar = '[' + '=' * filled + ' ' * (width - filled) + ']'
    percentage = f" {int(progress * 100)}%"
    return bar + percentage
