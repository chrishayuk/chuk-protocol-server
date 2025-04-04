#!/usr/bin/env python3
# tests/transports/websocket/test_monitorable_adapter.py

import asyncio
import uuid
import pytest

from chuk_protocol_server.transports.websocket.ws_monitorable_adapter import MonitorableWebSocketAdapter

# --- Dummy Implementations ---

class DummySessionMonitor:
    def __init__(self):
        self.registered = {}
        self.events = []
        self.unregistered = []

    async def register_session(self, session_id, client_info):
        self.registered[session_id] = client_info

    async def unregister_session(self, session_id):
        self.unregistered.append(session_id)

    async def broadcast_session_event(self, session_id, event_type, data):
        self.events.append((session_id, event_type, data))

class DummyHandlerForAdapter:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.called = False
        self.sent_lines = []
        self.mode = None
        self.server = None
        self.welcome_message = None

    async def handle_client(self):
        self.called = True

    async def send_line(self, message: str):
        self.sent_lines.append(message)

    async def cleanup(self):
        pass

class DummyMonitorableReader:
    def __init__(self, websocket):
        self.websocket = websocket
        self.session_id = None

class DummyWriter:
    def __init__(self, websocket):
        self.websocket = websocket
        self.writes = []

    async def write(self, data: bytes):
        self.writes.append(data)

    async def drain(self):
        pass

    def close(self):
        self._closed = True

    async def wait_closed(self):
        self._closed = True

# --- Dummy WebSocket ---
class DummyWebSocket:
    def __init__(self, remote_address=("127.0.0.1", 1111)):
        self.remote_address = remote_address
        self.request = type("DummyRequest", (), {"path": "/dummy"})
        self.request_headers = {"User-Agent": "DummyAgent"}

    def extra_method(self):
        return "extra_value"

# --- Fixtures ---
@pytest.fixture
def dummy_monitor():
    return DummySessionMonitor()

@pytest.fixture
def dummy_websocket():
    return DummyWebSocket()

@pytest.fixture
def adapter(monkeypatch, dummy_websocket):
    # Patch the MonitorableWebSocketReader and WebSocketWriter used by the adapter.
    monkeypatch.setattr(
        "chuk_protocol_server.transports.websocket.ws_monitorable_adapter.MonitorableWebSocketReader",
        DummyMonitorableReader,
    )
    monkeypatch.setattr(
        "chuk_protocol_server.transports.websocket.ws_monitorable_adapter.WebSocketWriter",
        lambda ws: DummyWriter(ws)
    )
    # Create the adapter with DummyHandlerForAdapter.
    return MonitorableWebSocketAdapter(dummy_websocket, handler_class=DummyHandlerForAdapter)

# --- Tests ---

def test_initialization(adapter, dummy_websocket):
    """
    Verify that upon initialization the adapter:
      - Uses the provided websocket,
      - Defaults to "telnet" mode,
      - Generates a session ID (as a valid UUID),
      - Passes the session ID to its reader.
    """
    assert adapter.websocket is dummy_websocket
    assert adapter.mode == "telnet"
    session_id = adapter.session_id
    assert isinstance(session_id, str)
    try:
        uuid_obj = uuid.UUID(session_id)
    except Exception:
        pytest.fail("session_id is not a valid UUID")
    assert adapter.reader.session_id == session_id

@pytest.mark.asyncio
async def test_handle_client_with_monitoring(monkeypatch, adapter, dummy_monitor):
    """
    Test that when monitoring is enabled, handle_client() registers the session,
    calls the handler's handle_client(), and unregisters the session afterward.
    """
    adapter.monitor = dummy_monitor
    adapter.is_monitored = True
    adapter.handler_class = DummyHandlerForAdapter
    await adapter.handle_client()
    session_id = adapter.session_id
    assert session_id in dummy_monitor.registered
    assert session_id in dummy_monitor.unregistered
    assert adapter.handler.called is True

@pytest.mark.asyncio
async def test_send_line_with_monitoring(monkeypatch, adapter, dummy_monitor):
    """
    Test that send_line() broadcasts the outgoing message and then
    sends it to the client (via the handler's send_line if available).
    """
    adapter.monitor = dummy_monitor
    adapter.is_monitored = True
    dummy_handler = DummyHandlerForAdapter(adapter.reader, adapter.writer)
    dummy_handler.sent_lines = []
    adapter.handler = dummy_handler

    test_message = "Test welcome"
    dummy_monitor.events.clear()

    await adapter.send_line(test_message)
    assert dummy_monitor.events, "No event broadcast by send_line"
    session_id, event_type, data = dummy_monitor.events[0]
    assert event_type == "server_message"
    assert data["text"] == test_message
    assert dummy_handler.sent_lines == [test_message]

@pytest.mark.asyncio
async def test_send_line_without_handler(monkeypatch, adapter, dummy_monitor):
    """
    Test that if no handler exists, send_line() writes directly using the writer.
    """
    adapter.monitor = dummy_monitor
    adapter.is_monitored = True
    adapter.handler = None
    dummy_writer = DummyWriter(adapter.websocket)
    adapter.writer = dummy_writer
    test_message = "Direct line"
    dummy_monitor.events.clear()

    await adapter.send_line(test_message)
    assert dummy_monitor.events, "No monitor event on send_line without handler"
    expected = (test_message + "\r\n").encode("utf-8")
    assert expected in dummy_writer.writes

@pytest.mark.asyncio
async def test_write_with_monitoring(monkeypatch, adapter, dummy_monitor):
    """
    Test that write() broadcasts raw write data when monitoring is enabled,
    and then forwards the data to the underlying writer.
    """
    adapter.monitor = dummy_monitor
    adapter.is_monitored = True
    dummy_writer = DummyWriter(adapter.websocket)
    adapter.writer = dummy_writer

    test_data = "Raw data test".encode("utf-8")
    dummy_monitor.events.clear()

    await adapter.write(test_data)
    assert dummy_monitor.events, "No monitor event on write()"
    session_id, event_type, data = dummy_monitor.events[0]
    assert event_type == "server_message"
    assert data["text"] == "Raw data test"
    assert test_data in dummy_writer.writes

@pytest.mark.asyncio
async def test_handle_client_without_monitoring(monkeypatch, adapter, dummy_monitor):
    """
    Test that if monitoring is disabled, handle_client() does not attempt session registration.
    """
    adapter.monitor = None
    adapter.is_monitored = False
    adapter.handler_class = DummyHandlerForAdapter

    await adapter.handle_client()
    assert dummy_monitor.events == []
    assert adapter.handler.called is True

def test_getattr_forwarding(monkeypatch, adapter, dummy_websocket):
    """
    Test that __getattr__ forwards attribute lookups to the underlying WebSocket.
    """
    # Use the adapter's __getattr__ method explicitly.
    forwarded = adapter.__getattr__("extra_method")
    assert forwarded is not None, "extra_method not forwarded"
    result = forwarded()
    assert result == "extra_value"
