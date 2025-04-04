#!/usr/bin/env python3
# tests/transports/websocket/test_ws_session_monitor.py
import asyncio
import json
import pytest

from chuk_protocol_server.transports.websocket.ws_session_monitor import SessionMonitor

# --- Dummy WebSocket for viewer connections ---
class DummyViewerWebSocket:
    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send(self, message: str):
        self.sent_messages.append(message)

# --- Tests for SessionMonitor ---

def test_is_monitor_path_default():
    monitor = SessionMonitor(path="/monitor")
    assert monitor.is_monitor_path("/monitor") is True
    assert monitor.is_monitor_path("monitor") is False
    assert monitor.is_monitor_path("/other") is False

@pytest.mark.asyncio
async def test_register_session(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    broadcast_calls = []

    async def dummy_broadcast_all(message):
        broadcast_calls.append(message)
    # Monkeypatch _broadcast_to_all_viewers to record its input.
    monkeypatch.setattr(monitor, "_broadcast_to_all_viewers", dummy_broadcast_all)

    # Register a session.
    session_id = "session-1"
    client_info = {"ip": "127.0.0.1", "port": 1234}
    await monitor.register_session(session_id, client_info)

    # Verify that the new session is stored with is_newest True.
    assert session_id in monitor.active_sessions
    session = monitor.active_sessions[session_id]
    assert session["client"] == client_info
    assert session["status"] == "connected"
    assert session["is_newest"] is True

    # Since there were no previous sessions, broadcast should have been called once.
    assert len(broadcast_calls) == 1
    # The broadcast message should be a dict with type 'session_started'
    assert broadcast_calls[0]["type"] == "session_started"
    assert broadcast_calls[0]["session"]["id"] == session_id

@pytest.mark.asyncio
async def test_unregister_session(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    broadcast_all = []
    broadcast_session = []

    async def dummy_broadcast_all(message):
        broadcast_all.append(message)

    async def dummy_broadcast_session(session_id, message):
        broadcast_session.append((session_id, message))

    monkeypatch.setattr(monitor, "_broadcast_to_all_viewers", dummy_broadcast_all)
    monkeypatch.setattr(monitor, "_broadcast_to_session_viewers", dummy_broadcast_session)

    # Pre-register a session.
    session_id = "session-2"
    client_info = {"ip": "192.168.1.1", "port": 4321}
    await monitor.register_session(session_id, client_info)
    # Clear broadcast calls from registration.
    broadcast_all.clear()
    # Also add a dummy viewer for this session.
    dummy_viewer = DummyViewerWebSocket()
    monitor.session_viewers[session_id] = {dummy_viewer}

    # Now unregister the session.
    await monitor.unregister_session(session_id)

    # Check that _broadcast_to_all_viewers was called with a session_ended message.
    # Now we expect only one broadcast (from unregistering).
    assert len(broadcast_all) == 1, f"Expected 1 broadcast call, got {len(broadcast_all)}: {broadcast_all}"
    msg = broadcast_all[0]
    assert msg["type"] == "session_ended"
    assert msg["session"]["id"] == session_id
    # Also, _broadcast_to_session_viewers should have been called.
    assert len(broadcast_session) == 1
    sid, sess_msg = broadcast_session[0]
    assert sid == session_id
    assert sess_msg["type"] == "session_ended"
    # The session should now be removed.
    assert session_id not in monitor.active_sessions
    assert session_id not in monitor.session_viewers

@pytest.mark.asyncio
async def test_broadcast_session_event(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    # Pre-register a session.
    session_id = "session-3"
    client_info = {"ip": "10.0.0.1", "port": 5555}
    await monitor.register_session(session_id, client_info)

    broadcast_calls = []

    async def dummy_broadcast_session(session_id_arg, message):
        broadcast_calls.append((session_id_arg, message))

    monkeypatch.setattr(monitor, "_broadcast_to_session_viewers", dummy_broadcast_session)

    # Broadcast an event.
    await monitor.broadcast_session_event(session_id, "client_event", {"key": "value"})
    assert len(broadcast_calls) == 1
    sid, msg = broadcast_calls[0]
    assert sid == session_id
    assert msg["type"] == "client_event"
    assert msg["session_id"] == session_id
    assert msg["data"]["key"] == "value"

@pytest.mark.asyncio
async def test_send_active_sessions(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    # Pre-register two sessions.
    await monitor.register_session("s1", {"ip": "1.1.1.1", "port": 1000})
    await monitor.register_session("s2", {"ip": "2.2.2.2", "port": 2000})

    # Create a dummy viewer with a dummy send() method that records messages.
    class DummyViewer:
        def __init__(self):
            self.sent = []
        async def send(self, message: str):
            self.sent.append(message)
    viewer = DummyViewer()

    await monitor._send_active_sessions(viewer)
    # The viewer should have received a JSON message.
    assert len(viewer.sent) == 1
    msg = json.loads(viewer.sent[0])
    assert msg["type"] == "active_sessions"
    # There should be 2 active sessions.
    assert len(msg["sessions"]) == 2

@pytest.mark.asyncio
async def test_process_viewer_command_watch(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    # Pre-register a session.
    session_id = "session-watch"
    await monitor.register_session(session_id, {"ip": "3.3.3.3", "port": 3000})
    # Set up session_viewers.
    monitor.session_viewers[session_id] = set()

    # Create a dummy viewer that records sent messages.
    class DummyViewer:
        def __init__(self):
            self.sent = []
        async def send(self, message: str):
            self.sent.append(message)
    viewer = DummyViewer()

    # Prepare a command to watch the session.
    command = {"type": "watch_session", "session_id": session_id}
    # Process the command.
    await monitor._process_viewer_command(viewer, command)
    # The viewer should now be added to session_viewers for that session.
    assert viewer in monitor.session_viewers[session_id]
    # Also, the viewer should have received a watch_response.
    assert len(viewer.sent) == 1
    response = json.loads(viewer.sent[0])
    assert response["type"] == "watch_response"
    assert response["session_id"] == session_id
    assert response["status"] == "success"

@pytest.mark.asyncio
async def test_process_viewer_command_stop(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    session_id = "session-stop"
    await monitor.register_session(session_id, {"ip": "4.4.4.4", "port": 4000})
    monitor.session_viewers[session_id] = set()
    # Create a dummy viewer and add it.
    class DummyViewer:
        def __init__(self):
            self.sent = []
        async def send(self, message: str):
            self.sent.append(message)
    viewer = DummyViewer()
    monitor.session_viewers[session_id].add(viewer)
    # Prepare a command to stop watching.
    command = {"type": "stop_watching", "session_id": session_id}
    await monitor._process_viewer_command(viewer, command)
    # The viewer should be removed.
    assert viewer not in monitor.session_viewers[session_id]
    # And should receive a response with status "stopped".
    assert len(viewer.sent) == 1
    response = json.loads(viewer.sent[0])
    assert response["type"] == "watch_response"
    assert response["status"] == "stopped"
    assert response["session_id"] == session_id

@pytest.mark.asyncio
async def test_broadcast_to_all_viewers(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    # Create two dummy viewers.
    class DummyViewer:
        def __init__(self):
            self.sent = []
            self.closed = False
        async def send(self, message: str):
            self.sent.append(message)
    viewer1 = DummyViewer()
    viewer2 = DummyViewer()
    monitor.all_viewers = {viewer1, viewer2}
    
    message = {"type": "test", "data": "value"}
    await monitor._broadcast_to_all_viewers(message)
    # Both viewers should have received the message.
    msg1 = json.loads(viewer1.sent[0])
    msg2 = json.loads(viewer2.sent[0])
    assert msg1 == message
    assert msg2 == message

@pytest.mark.asyncio
async def test_broadcast_to_session_viewers(monkeypatch):
    monitor = SessionMonitor(path="/monitor")
    session_id = "session-bcast"
    monitor.session_viewers[session_id] = set()
    # Create one dummy viewer.
    class DummyViewer:
        def __init__(self):
            self.sent = []
            self.closed = False
        async def send(self, message: str):
            self.sent.append(message)
    viewer = DummyViewer()
    monitor.session_viewers[session_id].add(viewer)
    
    message = {"type": "session_update", "status": "active"}
    await monitor._broadcast_to_session_viewers(session_id, message)
    # The viewer should receive the message.
    msg = json.loads(viewer.sent[0])
    assert msg == message
