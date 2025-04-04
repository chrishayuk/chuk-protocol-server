import os
import pytest
import yaml

from chuk_protocol_server.server_config import ServerConfig, TRANSPORT_TELNET, TRANSPORT_WEBSOCKET, TCP_TRANSPORT, WS_TELNET_TRANSPORT
from chuk_protocol_server.servers.telnet_server import TelnetServer
from chuk_protocol_server.servers.tcp_server import TCPServer
from chuk_protocol_server.servers.ws_server_plain import PlainWebSocketServer
from chuk_protocol_server.servers.ws_telnet_server import WSTelnetServer
from chuk_protocol_server.handlers.base_handler import BaseHandler

# Define a dummy handler that subclasses BaseHandler for testing purposes.
class DummyHandler(BaseHandler):
    async def handle_client(self):
        pass

#############################
# Tests for load_config()
#############################

def test_load_config_file_not_found(tmp_path):
    # Use a file path that does not exist.
    non_existent = tmp_path / "nonexistent.yaml"
    with pytest.raises(FileNotFoundError) as excinfo:
        ServerConfig.load_config(str(non_existent))
    assert "Configuration file not found" in str(excinfo.value)

def test_load_config_empty_file(tmp_path):
    # Create an empty YAML file.
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("")
    with pytest.raises(ValueError) as excinfo:
        ServerConfig.load_config(str(empty_file))
    assert "Empty or invalid configuration file" in str(excinfo.value)

def test_load_config_valid(tmp_path):
    # Create a valid YAML file.
    config_data = {
        "transport": TRANSPORT_TELNET,
        "handler_class": "DummyHandler",  # the value is not used by load_config
        "host": "127.0.0.1",
        "port": 8023
    }
    valid_file = tmp_path / "valid.yaml"
    valid_file.write_text(yaml.dump(config_data))
    
    loaded = ServerConfig.load_config(str(valid_file))
    assert isinstance(loaded, dict)
    assert loaded["transport"] == TRANSPORT_TELNET
    assert loaded["host"] == "127.0.0.1"
    assert loaded["port"] == 8023

#############################
# Tests for validate_config()
#############################

def test_validate_config_missing_required():
    # Missing both required fields.
    config = {}
    with pytest.raises(ValueError) as excinfo:
        ServerConfig.validate_config(config)
    assert "Missing required configuration field" in str(excinfo.value)

def test_validate_config_missing_handler_class():
    config = {
        "transport": TRANSPORT_TELNET
    }
    with pytest.raises(ValueError) as excinfo:
        ServerConfig.validate_config(config)
    assert "Missing required configuration field: handler_class" in str(excinfo.value)

def test_validate_config_invalid_transport():
    config = {
        "transport": "invalid_transport",
        "handler_class": "DummyHandler"
    }
    with pytest.raises(ValueError) as excinfo:
        ServerConfig.validate_config(config)
    assert "Invalid transport type" in str(excinfo.value)

def test_validate_config_ssl_enabled_missing_cert():
    config = {
        "transport": TRANSPORT_WEBSOCKET,
        "handler_class": "DummyHandler",
        "use_ssl": True  # Missing ssl_cert and ssl_key
    }
    with pytest.raises(ValueError) as excinfo:
        ServerConfig.validate_config(config)
    assert "SSL enabled but missing ssl_cert or ssl_key" in str(excinfo.value)

def test_validate_config_success():
    config = {
        "transport": TCP_TRANSPORT,
        "handler_class": "DummyHandler",
        "host": "192.168.1.10",
        "port": 9000,
        "use_ssl": False
    }
    # Should not raise any error.
    ServerConfig.validate_config(config)

#############################
# Tests for create_server_from_config()
#############################

@pytest.mark.parametrize("transport,expected_class", [
    (TRANSPORT_TELNET, TelnetServer),
    (TCP_TRANSPORT, TCPServer),
    (TRANSPORT_WEBSOCKET, PlainWebSocketServer),
    (WS_TELNET_TRANSPORT, WSTelnetServer)
])
def test_create_server_from_config(transport, expected_class):
    # Create a minimal valid configuration for each transport.
    config = {
        "transport": transport,
        "handler_class": "DummyHandler",  # placeholder; actual handler is passed as argument
        "host": "0.0.0.0",
        "port": 8080
    }
    # For WebSocket transports, add some extra keys.
    if transport in [TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]:
        config.update({
            "ws_path": "/ws_test",
            "ping_interval": 20,
            "ping_timeout": 5,
            "allow_origins": ["http://example.com"],
            "use_ssl": False,
            "enable_monitoring": True,
            "monitor_path": "/monitor_test"
        })
    
    server = ServerConfig.create_server_from_config(config, DummyHandler)
    assert isinstance(server, expected_class)
    # Verify that common properties are set.
    assert server.host == "0.0.0.0"
    assert server.port == 8080
    # Check that additional configuration parameters (if applicable) are set.
    if hasattr(server, "path"):
        if transport in [TRANSPORT_WEBSOCKET, WS_TELNET_TRANSPORT]:
            # For WebSocket servers, the path should be taken from ws_path.
            assert server.path == config.get("ws_path")
    # Optionally, check that a warning is logged for unknown keys (if any).
