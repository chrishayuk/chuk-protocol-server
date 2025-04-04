#!/usr/bin/env python3
# tests/transports/websocket/test_ws_monitorable_reader.py

import asyncio
import pytest

from chuk_protocol_server.transports.websocket.ws_monitorable_reader import MonitorableWebSocketReader

# --- Dummy Implementations ---

class DummyMonitor:
    def __init__(self):
        self.events = []

    async def broadcast_session_event(self, session_id, event_type, data):
        self.events.append((session_id, event_type, data))

class DummyWebSocket:
    def __init__(self):
        self.remote_address = ("127.0.0.1", 9999)

# Define dummy base methods to simulate underlying behavior.
async def dummy_read(self, n=-1):
    return b"Hello"

async def dummy_readline(self):
    return b"Line\n"

@pytest.fixture
def dummy_websocket():
    return DummyWebSocket()

@pytest.fixture
def dummy_monitor():
    return DummyMonitor()

@pytest.fixture
def monitorable_reader(dummy_websocket, dummy_monitor, monkeypatch):
    # Create an instance of MonitorableWebSocketReader.
    reader = MonitorableWebSocketReader(dummy_websocket)
    reader.session_id = "session-test"
    reader.monitor = dummy_monitor
    # Monkeypatch the parent's read and readline methods.
    # The base class is assumed to be WebSocketReader.
    monkeypatch.setattr(reader.__class__.__bases__[0], "read", dummy_read)
    monkeypatch.setattr(reader.__class__.__bases__[0], "readline", dummy_readline)
    return reader

# --- Tests ---

@pytest.mark.asyncio
async def test_read_broadcast(monitorable_reader, dummy_monitor):
    """
    When read() returns data, the reader should broadcast the client input.
    """
    data = await monitorable_reader.read()
    assert data == b"Hello"
    # Verify that an event was broadcast.
    assert dummy_monitor.events, "No broadcast event issued on read()"
    session_id, event_type, event_data = dummy_monitor.events[0]
    assert session_id == "session-test"
    assert event_type == "client_input"
    assert event_data["text"] == "Hello"

@pytest.mark.asyncio
async def test_readline_broadcast(monitorable_reader, dummy_monitor):
    """
    When readline() returns a line, the reader should broadcast the client input.
    """
    # Clear any existing events.
    dummy_monitor.events.clear()
    line = await monitorable_reader.readline()
    assert line == b"Line\n"
    # Verify that an event was broadcast.
    assert dummy_monitor.events, "No broadcast event issued on readline()"
    session_id, event_type, event_data = dummy_monitor.events[0]
    assert session_id == "session-test"
    assert event_type == "client_input"
    assert event_data["text"] == "Line\n"

@pytest.mark.asyncio
async def test_no_broadcast_for_empty(monitorable_reader, dummy_monitor, monkeypatch):
    """
    If the read returns data that is empty or only whitespace, no event should be broadcast.
    """
    async def dummy_read_empty(self, n=-1):
        return b"   "  # whitespace only
    monkeypatch.setattr(monitorable_reader.__class__.__bases__[0], "read", dummy_read_empty)
    dummy_monitor.events.clear()
    data = await monitorable_reader.read()
    assert data == b"   "
    # Expect no broadcast since the text is only whitespace.
    assert dummy_monitor.events == []
