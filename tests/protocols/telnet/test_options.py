#!/usr/bin/env python3
# tests/protocols/telnet/test_options.py

import pytest
from chuk_protocol_server.protocols.telnet.options import OptionManager

# For testing, define some dummy option codes.
OPT_TEST1 = 42
OPT_TEST2 = 43

def test_initial_state():
    opt_manager = OptionManager()
    assert opt_manager.local_options == {}
    assert opt_manager.remote_options == {}
    assert opt_manager._pending_local == set()
    assert opt_manager._pending_remote == set()

def test_initialize_options():
    opt_manager = OptionManager()
    options = [OPT_TEST1, OPT_TEST2]
    opt_manager.initialize_options(options)
    # Both local and remote should be initialized to False.
    assert opt_manager.local_options == {OPT_TEST1: False, OPT_TEST2: False}
    assert opt_manager.remote_options == {OPT_TEST1: False, OPT_TEST2: False}

def test_set_local_option_removes_pending():
    opt_manager = OptionManager()
    # Mark OPT_TEST1 as pending.
    opt_manager.mark_pending_local(OPT_TEST1)
    assert opt_manager.is_local_pending(OPT_TEST1) is True
    # Now, set it enabled.
    opt_manager.set_local_option(OPT_TEST1, True)
    assert opt_manager.is_local_enabled(OPT_TEST1) is True
    # It should be removed from pending.
    assert opt_manager.is_local_pending(OPT_TEST1) is False

def test_set_remote_option_removes_pending():
    opt_manager = OptionManager()
    opt_manager.mark_pending_remote(OPT_TEST2)
    assert opt_manager.is_remote_pending(OPT_TEST2) is True
    opt_manager.set_remote_option(OPT_TEST2, True)
    assert opt_manager.is_remote_enabled(OPT_TEST2) is True
    assert opt_manager.is_remote_pending(OPT_TEST2) is False

def test_mark_pending():
    opt_manager = OptionManager()
    opt_manager.mark_pending_local(OPT_TEST1)
    opt_manager.mark_pending_remote(OPT_TEST2)
    assert opt_manager.is_local_pending(OPT_TEST1) is True
    assert opt_manager.is_remote_pending(OPT_TEST2) is True

def test_get_option_status():
    # Option status string should include option name, and local/remote state.
    opt_manager = OptionManager()
    # Initialize the options.
    opt_manager.initialize_options([OPT_TEST1])
    # Enable OPT_TEST1 locally.
    opt_manager.set_local_option(OPT_TEST1, True)
    # Leave remote disabled.
    status = opt_manager.get_option_status(OPT_TEST1)
    # Adjust expected string to match the actual output from get_option_name.
    expected = "UNKNOWN-OPTION-42: local=enabled, remote=disabled"
    assert status == expected

def test_repr():
    opt_manager = OptionManager()
    opt_manager.initialize_options([OPT_TEST1])
    opt_manager.set_local_option(OPT_TEST1, True)
    r = repr(opt_manager)
    # The repr string should include the local and remote dicts.
    assert "local=" in r
    assert "remote=" in r
    assert str(OPT_TEST1) in r
