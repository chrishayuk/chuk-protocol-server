#!/usr/bin/env python3
# tests/transports/websocket/test_ws_interceptor.py

import asyncio
import pytest
from websockets.exceptions import ConnectionClosed

from chuk_protocol_server.transports.websocket.ws_interceptor import WebSocketInterceptor

# --- Dummy SessionMonitor ---
class DummySessionMonitor:
    def __init__(self):
        self.events = []

    async def broadcast_session_event(self, session_id, event_type, data):
        self.events.append((session_id, event_type, data))

# --- Dummy WebSocket ---
class DummyWebSocket:
    def __init__(self, messages=None, remote_address=("127.0.0.1", 9999)):
        # messages is a list of messages to be returned by recv()
        self._messages = messages or []
        self.sent_messages = []
        self.remote_address = remote_address

    async def recv(self):
        if self._messages:
            return self._messages.pop(0)
        # Simulate end-of-stream by raising ConnectionClosed with a valid third parameter.
        raise ConnectionClosed(1000, "dummy close", False)

    async def send(self, message):
        self.sent_messages.append(message)

    # To support attribute forwarding in __getattr__
    def extra_method(self):
        return "extra"

# --- Tests ---
@pytest.fixture
def dummy_monitor():
    return DummySessionMonitor()

@pytest.fixture
def dummy_websocket():
    # By default, set up a websocket with two messages.
    return DummyWebSocket(messages=["Hello", b"World"])

@pytest.fixture
def interceptor(dummy_websocket, dummy_monitor):
    # Create a WebSocketInterceptor with a dummy session id and monitor.
    return WebSocketInterceptor(dummy_websocket, session_id="session123", monitor=dummy_monitor)

@pytest.mark.asyncio
async def test_recv_interception_text(interceptor, dummy_monitor):
    # Test that recv() intercepts a text message.
    # The dummy_websocket (inside interceptor) is set to return "Hello".
    message = await interceptor.recv()
    # The received message should be "Hello"
    assert message == "Hello"
    # The monitor should have received a broadcast event with event type 'client_input'
    # and data containing the text.
    assert dummy_monitor.events
    session_id, event_type, data = dummy_monitor.events[0]
    assert session_id == "session123"
    assert event_type == "client_input"
    assert data["text"] == "Hello"

@pytest.mark.asyncio
async def test_recv_interception_bytes(interceptor, dummy_monitor):
    # Reset the dummy websocket with a bytes message.
    interceptor.websocket._messages = [b"ByteMessage"]
    # Clear previous events.
    dummy_monitor.events.clear()
    message = await interceptor.recv()
    # The received message should be the bytes object.
    assert message == b"ByteMessage"
    # The monitor should have received the broadcast event with the decoded text.
    assert dummy_monitor.events
    session_id, event_type, data = dummy_monitor.events[0]
    assert data["text"] == "ByteMessage"  # Decoded using 'replace'

@pytest.mark.asyncio
async def test_send_interception(interceptor, dummy_monitor):
    # Test that send() broadcasts an event then sends the message.
    test_msg = "Server says hi"
    # Clear any previous events.
    dummy_monitor.events.clear()
    await interceptor.send(test_msg)
    # Check that the monitor got an event with type 'server_message'
    assert dummy_monitor.events
    session_id, event_type, data = dummy_monitor.events[0]
    assert event_type == "server_message"
    assert data["text"] == test_msg
    # Also, the underlying websocket should have recorded the sent message.
    assert test_msg in interceptor.websocket.sent_messages

@pytest.mark.asyncio
async def test_async_iteration(interceptor):
    # Set up a dummy websocket that returns two messages then raises ConnectionClosed.
    messages = ["First", "Second"]
    interceptor.websocket._messages = messages.copy()
    received = []
    async for msg in interceptor:
        received.append(msg)
    # After iteration ends, received messages should match the list.
    assert received == messages

@pytest.mark.asyncio
async def test_getattr_forwarding(interceptor):
    # Test that attribute lookup is forwarded to the underlying websocket.
    # The DummyWebSocket defines an extra_method().
    result = interceptor.extra_method()
    assert result == "extra"
