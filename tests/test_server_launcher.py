import argparse
import asyncio
import os
import signal
import sys
import yaml
import logging
import importlib

import pytest

from chuk_protocol_server.server_launcher import (
    setup_logging,
    load_handler_class,
    create_server_instance,
    run_server,
    run_multiple_servers,
    shutdown_all_servers,
    setup_signal_handlers,
    async_main,
    main,
)
from chuk_protocol_server.handlers.base_handler import BaseHandler
from chuk_protocol_server.servers.base_server import BaseServer

# ---------------------------
# Dummy classes for testing
# ---------------------------

# Dummy handler that is a subclass of BaseHandler.
class DummyHandler(BaseHandler):
    async def handle_client(self):
        await asyncio.sleep(0)

# Dummy server class for testing; subclass BaseServer.
class DummyServer(BaseServer):
    def __init__(self, host="0.0.0.0", port=8023, handler_class=DummyHandler):
        self.host = host
        self.port = port
        self.handler_class = handler_class
        self._shutdown_called = False

    # Implement the abstract method _create_server so we can instantiate.
    async def _create_server(self):
        return None

    async def start_server(self):
        await asyncio.sleep(0)

    async def shutdown(self):
        self._shutdown_called = True

# ---------------------------
# Tests for server_launcher.py
# ---------------------------

def test_setup_logging():
    setup_logging(verbosity=2)
    logger = logging.getLogger('chuk-protocol-server')
    assert logger.level <= logging.DEBUG

def test_load_handler_class_success():
    module_name = "dummy_module"
    class_name = "DummyHandler"
    dummy_module = type("DummyModule", (), {})()
    setattr(dummy_module, class_name, DummyHandler)
    sys.modules[module_name] = dummy_module

    handler_path = f"{module_name}:{class_name}"
    cls = load_handler_class(handler_path)
    assert cls is DummyHandler

    del sys.modules[module_name]

def test_load_handler_class_failure():
    with pytest.raises(ValueError):
        load_handler_class("invalid_format")
    with pytest.raises(ValueError):
        load_handler_class("nonexistent:DummyHandler")
    module_name = "dummy_module2"
    class_name = "NotAHandler"
    dummy_module = type("DummyModule2", (), {})()
    setattr(dummy_module, class_name, object)
    sys.modules[module_name] = dummy_module
    with pytest.raises(TypeError) as excinfo:
        load_handler_class(f"{module_name}:{class_name}")
    assert f"{class_name} must be a subclass of BaseHandler" in str(excinfo.value)
    del sys.modules[module_name]

def test_create_server_instance(monkeypatch):
    from chuk_protocol_server.server_config import ServerConfig

    dummy_config = {"transport": "telnet", "host": "127.0.0.1", "port": 8000}
    def dummy_create_server_from_config(config, handler_class):
        return DummyServer(host=config.get("host"), port=config.get("port"), handler_class=handler_class)
    monkeypatch.setattr(ServerConfig, "create_server_from_config", dummy_create_server_from_config)
    
    server = create_server_instance(DummyHandler, dummy_config)
    assert isinstance(server, DummyServer)
    assert server.host == "127.0.0.1"
    assert server.port == 8000

@pytest.mark.asyncio
async def test_run_server():
    server = DummyServer()
    await run_server(server)

@pytest.mark.asyncio
async def test_run_multiple_servers():
    server1 = DummyServer()
    server2 = DummyServer()
    servers = [server1, server2]
    await run_multiple_servers(servers)

@pytest.mark.asyncio
async def test_shutdown_all_servers():
    server1 = DummyServer()
    server2 = DummyServer()
    servers = [server1, server2]
    await shutdown_all_servers(servers)
    assert server1._shutdown_called
    assert server2._shutdown_called

@pytest.mark.asyncio
async def test_setup_signal_handlers(monkeypatch):
    loop = asyncio.get_running_loop()
    servers = [DummyServer()]
    shutdown_called = False
    async def dummy_shutdown_all(servers):
        nonlocal shutdown_called
        shutdown_called = True
    monkeypatch.setattr("chuk_protocol_server.server_launcher.shutdown_all_servers", dummy_shutdown_all)
    
    # Replace loop.add_signal_handler to capture callbacks in our own dictionary.
    captured_signals = {}
    def fake_add_signal_handler(sig, callback, *args):
        captured_signals[sig] = callback
    monkeypatch.setattr(loop, "add_signal_handler", fake_add_signal_handler)
    
    setup_signal_handlers(loop, servers)
    
    # Invoke each captured callback.
    for sig in (signal.SIGINT, signal.SIGTERM):
        if sig in captured_signals:
            captured_signals[sig]()
    await asyncio.sleep(0.1)
    assert shutdown_called

@pytest.mark.asyncio
async def test_async_main_without_config(monkeypatch, tmp_path):
    args = argparse.Namespace(
        handler="dummy_module:DummyHandler",
        config=None,
        host="127.0.0.1",
        port=9000,
        transport="telnet",
        verbose=2
    )
    module_name = "dummy_module"
    dummy_module = type("DummyModule", (), {})()
    setattr(dummy_module, "DummyHandler", DummyHandler)
    sys.modules[module_name] = dummy_module

    from chuk_protocol_server.server_config import ServerConfig
    def dummy_create_server_from_config(config, handler_class):
        return DummyServer(host=config.get("host"), port=config.get("port"), handler_class=handler_class)
    monkeypatch.setattr(ServerConfig, "create_server_from_config", dummy_create_server_from_config)
    monkeypatch.setattr("chuk_protocol_server.server_launcher.run_multiple_servers", lambda servers: asyncio.sleep(0))
    
    ret = await async_main(args)
    assert ret == 0
    del sys.modules[module_name]

@pytest.mark.asyncio
async def test_async_main_with_config(monkeypatch, tmp_path):
    config_dict = {
        "transport": "telnet",
        "handler_class": "dummy_module:DummyHandler",
        "host": "0.0.0.0",
        "port": 8001
    }
    config_file = tmp_path / "server.yaml"
    config_file.write_text(yaml.dump(config_dict))
    
    args = argparse.Namespace(
        handler=None,
        config=str(config_file),
        host="127.0.0.1",
        port=9000,
        transport="tcp",  # CLI override
        verbose=1
    )
    module_name = "dummy_module"
    dummy_module = type("DummyModule", (), {})()
    setattr(dummy_module, "DummyHandler", DummyHandler)
    sys.modules[module_name] = dummy_module

    from chuk_protocol_server.server_config import ServerConfig
    def dummy_create_server_from_config(config, handler_class):
        return DummyServer(host=config.get("host"), port=config.get("port"), handler_class=handler_class)
    monkeypatch.setattr(ServerConfig, "create_server_from_config", dummy_create_server_from_config)
    monkeypatch.setattr("chuk_protocol_server.server_launcher.run_multiple_servers", lambda servers: asyncio.sleep(0))
    
    ret = await async_main(args)
    assert ret == 0
    del sys.modules[module_name]

def test_main(monkeypatch, tmp_path):
    config_dict = {
        "transport": "telnet",
        "handler_class": "dummy_module:DummyHandler",
        "host": "0.0.0.0",
        "port": 8002
    }
    config_file = tmp_path / "server.yaml"
    config_file.write_text(yaml.dump(config_dict))
    
    test_args = [
        "server_launcher.py",
        "--config", str(config_file),
        "-v"
    ]
    monkeypatch.setattr(sys, "argv", test_args)
    
    # Patch async_main so that it returns a coroutine yielding 0.
    async def fake_async_main(args):
        return 0
    monkeypatch.setattr("chuk_protocol_server.server_launcher.async_main", fake_async_main)
    
    ret = main()
    # Since __name__ != "__main__", main() returns the value instead of calling sys.exit.
    assert ret == 0
