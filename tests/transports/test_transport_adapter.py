#!/usr/bin/env python3
# tests/transports/transport_adapter/test_transport_adapter.py

import asyncio
import pytest

from chuk_protocol_server.transports.transport_adapter import (
    StreamReaderAdapter,
    StreamWriterAdapter,
    BaseTransportAdapter,
)
from chuk_protocol_server.handlers.base_handler import BaseHandler

# --- Dummy Subclasses ---

class DummyReaderAdapter(StreamReaderAdapter):
    pass

class DummyWriterAdapter(StreamWriterAdapter):
    pass

class DummyTransportAdapter(BaseTransportAdapter):
    pass

class DummyHandler(BaseHandler):
    async def handle_client(self):
        pass

# --- Tests for StreamReaderAdapter ---

def test_stream_reader_adapter_read():
    reader = DummyReaderAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(reader.read())

def test_stream_reader_adapter_readline():
    reader = DummyReaderAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(reader.readline())

def test_stream_reader_adapter_at_eof():
    reader = DummyReaderAdapter()
    with pytest.raises(NotImplementedError):
        reader.at_eof()

# --- Tests for StreamWriterAdapter ---

def test_stream_writer_adapter_write():
    writer = DummyWriterAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(writer.write(b"test"))

def test_stream_writer_adapter_drain():
    writer = DummyWriterAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(writer.drain())

def test_stream_writer_adapter_close():
    writer = DummyWriterAdapter()
    with pytest.raises(NotImplementedError):
        writer.close()

def test_stream_writer_adapter_wait_closed():
    writer = DummyWriterAdapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(writer.wait_closed())

def test_stream_writer_adapter_get_extra_info():
    writer = DummyWriterAdapter()
    # Since the default get_extra_info just returns the default, test that.
    assert writer.get_extra_info("nonexistent", default="default") == "default"

# --- Tests for BaseTransportAdapter ---

def test_base_transport_adapter_handle_client():
    adapter = DummyTransportAdapter(DummyHandler)
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.handle_client())

def test_base_transport_adapter_send_line():
    adapter = DummyTransportAdapter(DummyHandler)
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.send_line("Hello"))

def test_base_transport_adapter_close():
    adapter = DummyTransportAdapter(DummyHandler)
    with pytest.raises(NotImplementedError):
        asyncio.run(adapter.close())
