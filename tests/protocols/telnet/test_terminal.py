#!/usr/bin/env python3
# tests/protocols/telnet/test_terminal.py

import pytest
from chuk_protocol_server.protocols.telnet.terminal import TerminalInfo

# --- Tests for TerminalInfo ---

def test_default_values():
    term = TerminalInfo()
    # Default terminal type is "UNKNOWN"
    assert term.term_type == "UNKNOWN"
    # Default dimensions
    assert term.width == 80
    assert term.height == 24
    # Default capabilities: all False
    assert term.capabilities == {'color': False, 'graphics': False, 'utf8': False}
    # Terminal info not yet received
    assert term.terminal_info_received is False

def test_set_terminal_type_infers_capabilities():
    term = TerminalInfo()
    # Set terminal type to a value that supports color, graphics, and utf8.
    term.set_terminal_type("xterm-256color")
    assert term.term_type == "xterm-256color"
    assert term.terminal_info_received is True
    # According to the inference rules, xterm-256color should have color, graphics, and UTF-8 support.
    assert term.capabilities['color'] is True
    assert term.capabilities['graphics'] is True
    assert term.capabilities['utf8'] is True

def test_set_terminal_type_no_capabilities():
    term = TerminalInfo()
    term.set_terminal_type("vt100")
    # vt100 might not contain "color", "xterm", "256", or "ansi" in lowercase.
    # So capabilities['color'] should be False.
    assert term.term_type == "vt100"
    assert term.capabilities['color'] is False
    # Graphics and utf8 support are inferred from xterm or similar.
    assert term.capabilities['graphics'] is False
    assert term.capabilities['utf8'] is False

def test_set_window_size_bounds():
    term = TerminalInfo()
    # Set values below minimum.
    term.set_window_size(5, 1)
    # Should default to 80x24
    assert term.width == 80
    assert term.height == 24

    # Set valid window size.
    term.set_window_size(100, 40)
    assert term.width == 100
    assert term.height == 40

def test_window_size_property():
    term = TerminalInfo()
    term.set_window_size(120, 30)
    assert term.window_size == (120, 30)

def test_has_capabilities():
    term = TerminalInfo()
    # Initially, capabilities are all False.
    assert term.has_color() is False
    assert term.has_graphics() is False
    assert term.has_utf8() is False

    # Set terminal type that implies color and utf8.
    term.set_terminal_type("ansi")
    assert term.has_color() is True
    # ansi may not imply graphics support.
    assert term.has_graphics() is False
    assert term.has_utf8() is True

def test_get_terminal_summary_not_received():
    term = TerminalInfo()
    summary = term.get_terminal_summary()
    assert summary == "Terminal information not yet received"

def test_get_terminal_summary_received():
    term = TerminalInfo()
    term.set_terminal_type("xterm")
    term.set_window_size(100, 50)
    summary = term.get_terminal_summary()
    expected = (
        "Terminal: xterm, Size: 100x50, Color: Yes, Graphics: Yes, UTF-8: Yes"
    )
    assert summary == expected

def test_repr_contains_info():
    term = TerminalInfo()
    term.set_terminal_type("vt100")
    term.set_window_size(80, 24)
    rep = repr(term)
    assert "TerminalInfo(" in rep
    assert "vt100" in rep
    assert "80x24" in rep
    assert "capabilities=" in rep

def test_process_terminal_type_data_valid():
    term = TerminalInfo()
    # Valid subnegotiation data: first byte 0, then terminal type string in ASCII.
    data = bytes([0]) + b"xterm"
    term.process_terminal_type_data(data)
    assert term.term_type == "xterm"
    assert term.terminal_info_received is True
    # Check that capabilities are inferred.
    assert term.has_color() is True
    assert term.has_graphics() is True
    assert term.has_utf8() is True

def test_process_terminal_type_data_invalid():
    term = TerminalInfo()
    # Invalid data: first byte not 0.
    data = b"\x01xterm"
    term.process_terminal_type_data(data)
    # Terminal type should remain unchanged.
    assert term.term_type == "UNKNOWN"
    # Warning should be logged (not tested here, but behavior is to do nothing).

def test_process_window_size_data_valid():
    term = TerminalInfo()
    # Provide 4 bytes representing width and height.
    # For example, width = 100 (0x0064), height = 50 (0x0032)
    data = bytes([0x00, 0x64, 0x00, 0x32])
    term.process_window_size_data(data)
    assert term.width == 100
    assert term.height == 50

def test_process_window_size_data_invalid():
    term = TerminalInfo()
    # Provide fewer than 4 bytes.
    data = bytes([0x00, 0x50])
    # The window size should remain at its default.
    term.process_window_size_data(data)
    assert term.width == 80
    assert term.height == 24
