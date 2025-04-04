import pytest
from chuk_protocol_server.utils.terminal_codes import (
    Color, 
    erase_char, 
    erase_line, 
    erase_screen, 
    move_cursor, 
    move_up, 
    move_down, 
    move_right, 
    move_left, 
    set_color, 
    reset_colors, 
    set_title, 
    get_colored_text,
    hide_cursor,
    show_cursor,
    save_cursor_position,
    restore_cursor_position,
    create_progress_bar
)

def test_erase_char():
    """Test the erase_char function."""
    assert erase_char() == b'\b \b'

def test_erase_line():
    """Test the erase_line function."""
    assert erase_line() == b'\x1b[2K\r'

def test_erase_screen():
    """Test the erase_screen function."""
    assert erase_screen() == b'\x1b[2J'

def test_move_cursor():
    """Test the move_cursor function."""
    # Test basic positioning
    assert move_cursor(5, 10) == b'\x1b[10;5H'
    
    # Test edge cases
    assert move_cursor(1, 1) == b'\x1b[1;1H'

def test_move_direction_functions():
    """Test cursor movement functions."""
    # Default movement (1 step)
    assert move_up() == b'\x1b[1A'
    assert move_down() == b'\x1b[1B'
    assert move_right() == b'\x1b[1C'
    assert move_left() == b'\x1b[1D'
    
    # Multiple steps
    assert move_up(5) == b'\x1b[5A'
    assert move_down(3) == b'\x1b[3B'
    assert move_right(7) == b'\x1b[7C'
    assert move_left(2) == b'\x1b[2D'

def test_set_color():
    """Test the set_color function."""
    # No color
    assert set_color() == b'\x1b[0m'
    
    # Foreground color
    assert set_color(fg=Color.RED) == b'\x1b[31m'
    
    # Background color
    assert set_color(bg=Color.GREEN) == b'\x1b[42m'
    
    # Foreground and background
    assert set_color(fg=Color.BLUE, bg=Color.YELLOW) == b'\x1b[34;43m'
    
    # With effects
    assert set_color(fg=Color.MAGENTA, effects=[Color.BOLD, Color.UNDERLINE]) == b'\x1b[1;4;35m'

def test_reset_colors():
    """Test the reset_colors function."""
    assert reset_colors() == b'\x1b[0m'

def test_set_title():
    """Test the set_title function."""
    assert set_title("Test Window") == b'\x1b]0;Test Window\x07'

def test_get_colored_text():
    """Test the get_colored_text function."""
    # Basic colored text
    assert get_colored_text("Hello", fg=Color.GREEN) == b'\x1b[32mHello\x1b[0m'
    
    # With effects
    assert get_colored_text("World", fg=Color.RED, effects=[Color.BOLD]) == b'\x1b[1;31mWorld\x1b[0m'

def test_cursor_visibility():
    """Test cursor visibility functions."""
    assert hide_cursor() == b'\x1b[?25l'
    assert show_cursor() == b'\x1b[?25h'

def test_cursor_position_save_restore():
    """Test saving and restoring cursor position."""
    assert save_cursor_position() == b'\x1b[s'
    assert restore_cursor_position() == b'\x1b[u'

def test_create_progress_bar():
    """Test the create_progress_bar function."""
    # 0% progress
    assert create_progress_bar(10, 0.0) == '[          ] 0%'
    
    # 50% progress
    assert create_progress_bar(10, 0.5) == '[=====     ] 50%'
    
    # 100% progress
    assert create_progress_bar(10, 1.0) == '[==========] 100%'
    
    # Out of bounds progress
    assert create_progress_bar(10, -0.5) == '[          ] 0%'
    assert create_progress_bar(10, 1.5) == '[==========] 100%'

def test_color_constants():
    """Test the Color class constants."""
    # Text Colors
    assert Color.BLACK == 0
    assert Color.RED == 1
    assert Color.GREEN == 2
    assert Color.YELLOW == 3
    assert Color.BLUE == 4
    assert Color.MAGENTA == 5
    assert Color.CYAN == 6
    assert Color.WHITE == 7
    
    # Text Formatting
    assert Color.RESET == 0
    assert Color.BOLD == 1
    assert Color.DIM == 2
    assert Color.ITALIC == 3
    assert Color.UNDERLINE == 4
    assert Color.BLINK == 5
    assert Color.REVERSE == 7
    assert Color.HIDDEN == 8
    assert Color.STRIKE == 9