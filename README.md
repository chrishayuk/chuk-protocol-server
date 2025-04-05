# CHUK Protocol Server

A modern Python framework for building server applications that work across multiple transport protocols: Telnet, TCP, and WebSocket. Create a server once and make it accessible from traditional terminal clients, command-line tools, and web browsers.

## Features

- **Multiple Transport Protocols**: Run your server on Telnet, TCP, and WebSocket simultaneously
- **Unified Handler Interface**: Write your application logic once, deploy everywhere
- **Configurable**: YAML-based configuration with transport-specific options
- **Graceful Shutdown**: Proper connection handling and clean termination
- **Protocol Detection**: Automatic Telnet negotiation detection with fallback
- **Session Management**: Connection limits, timeouts, and custom welcome messages
- **Async Architecture**: Built on Python's asyncio for efficient handling of concurrent connections
- **Proper Telnet Protocol Implementation**: Full support for telnet option negotiation and subnegotiation
- **Dual-Mode Operation**: Supports both line mode and character mode terminal handling
- **Robust Error Handling**: Graceful handling of connection issues and unexpected client behavior
- **Session Monitoring**: Optional monitoring of WebSocket sessions for debugging and analysis

## Requirements

- Python 3.7+
- Dependencies:
  - websockets
  - pyyaml
  - asyncio

## Installation

```bash
# Install from PyPI
pip install chuk-protocol-server

# Or install from source
git clone https://github.com/yourusername/chuk-protocol-server.git
cd chuk-protocol-server
pip install -e .

# Optional: Install development dependencies
pip install -e ".[dev]"
```

## Quick Start

1. Create a handler class that inherits from one of the base handlers
2. Configure your server with a YAML file
3. Launch your server using the server launcher

```bash
uv run server-launcher -c src/chuk_protocol_server/sample_servers/echo_server/config.yaml
```

## Client Connections

Your server will be accessible from multiple client types:

### Telnet Client

Connect to the Telnet transport using a traditional Telnet client:

```bash
telnet localhost 8023
```

The server will negotiate Telnet options and provide a full-featured terminal experience.

### TCP Client (netcat)

Connect to the TCP transport using netcat or similar tools:

```bash
nc localhost 8024
```

This provides a simple line-based interface without Telnet negotiation.

### WebSocket Client

Connect to the WebSocket transport using any WebSocket client:

#### Command-line with websocat

```bash
# Install websocat if needed (https://github.com/vi/websocat)
websocat --exit-on-eof ws://localhost:8025/ws
```

#### Browser JavaScript

```javascript
const ws = new WebSocket('ws://localhost:8025/ws');
ws.onmessage = function(event) { console.log('Received:', event.data); };
ws.onopen = function() { console.log('Connected!'); };
ws.onclose = function() { console.log('Disconnected'); };

// Send a message
ws.send('hello');
```

## Configuration

The framework uses YAML configuration files for server setup:

```yaml
# Single server configuration
host: 0.0.0.0
port: 8023
transport: telnet
handler_class: sample_servers.echo_server:EchoTelnetHandler

# OR 

# Multi-transport configuration
servers:
  telnet:
    host: "0.0.0.0"
    port: 8023
    transport: "telnet"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the Telnet Server!"

  tcp:
    host: "0.0.0.0"
    port: 8024
    transport: "tcp"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the TCP Server!"

  websocket:
    host: "0.0.0.0"
    port: 8025
    transport: "websocket"
    ws_path: "/ws"
    handler_class: "sample_servers.echo_server:EchoTelnetHandler"
    use_ssl: false
    allow_origins:
      - "*"
    max_connections: 100
    connection_timeout: 300
    welcome_message: "Welcome to the WebSocket Server!"
    enable_monitoring: true
    monitor_path: "/monitor"
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| host | Bind address | 0.0.0.0 |
| port | Listen port | 8023 |
| transport | Protocol type (telnet, tcp, websocket, ws_telnet) | telnet |
| handler_class | Handler class path (module:ClassName) | Required |
| max_connections | Maximum concurrent connections | 100 |
| connection_timeout | Session timeout in seconds | 300 |
| welcome_message | Message displayed on connection | None |
| ws_path | Path for WebSocket endpoint | /ws |
| allow_origins | CORS allowed origins | ["*"] |
| use_ssl | Enable SSL/TLS (WebSocket) | false |
| ssl_cert | Path to SSL certificate | None |
| ssl_key | Path to SSL key | None |
| ping_interval | WebSocket ping interval in seconds | 30 |
| ping_timeout | WebSocket ping timeout in seconds | 10 |
| enable_monitoring | Enable session monitoring (WebSocket) | false |
| monitor_path | Path for monitoring endpoint | /monitor |

## Creating Handlers

Handlers define your server's behavior. Extend one of the base handler classes:

```python
#!/usr/bin/env python3
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

class EchoTelnetHandler(TelnetHandler):
    async def on_command_submitted(self, command: str) -> None:
        if command.lower() == 'help':
            await self.send_line("Available commands: help, info, quit")
        else:
            await self.send_line(f"Echo: {command}")

    async def process_line(self, line: str) -> bool:
        if line.lower() in ['quit', 'exit', 'q']:
            await self.end_session("Goodbye!")
            return False
        await self.on_command_submitted(line)
        await self.show_prompt()
        return True
```

For more advanced customization, override additional methods:

```python
class AdvancedHandler(TelnetHandler):
    def __init__(self, reader, writer):
        super().__init__(reader, writer)
        self.custom_state = {}

    async def show_prompt(self) -> None:
        # Customize the prompt
        await self.send_raw(b"my-app> ")

    async def process_character(self, char: str) -> bool:
        # Custom character processing
        # Return False to terminate the connection
        return await super().default_process_character(char)
```

## Handler Classes

The framework provides several handler classes that you can extend:

- **BaseHandler**: Basic connection handling with raw I/O
- **CharacterHandler**: Character-by-character processing for interactive applications
- **LineHandler**: Line-by-line processing for simpler command interfaces
- **TelnetHandler**: Full telnet protocol support with negotiation

Choose the appropriate base class based on your application's needs.

## Architecture

The framework is built on a layered architecture:

1. **Servers**: Handle transport-specific connection management (Telnet, TCP, WebSocket)
2. **Handlers**: Process client input and generate responses
3. **Adapters**: Bridge between different transport types and handlers

This modular design allows for:

- **Transport Layer**: Manages network protocols and connections
- **Character Protocol Layer**: Character-by-character reading and processing
- **Telnet Protocol Layer**: Telnet-specific protocol handling and negotiation
- **Application Logic Layer**: Custom application behavior

## Running the Server

Launch your server with the server launcher module:

```bash
# With a configuration file
python -m chuk_protocol_server.server_launcher -c config/my_server.yaml

# Direct handler specification
python -m chuk_protocol_server.server_launcher my_package.handlers:MyHandler --port 8000

# Verbose logging
python -m chuk_protocol_server.server_launcher -c config/my_server.yaml -vv
```

## Example Handlers

Here are examples of handlers for different use cases:

### Echo Server Handler

```python
from chuk_protocol_server.handlers.telnet_handler import TelnetHandler

class EchoHandler(TelnetHandler):
    async def on_command_submitted(self, command: str) -> None:
        await self.send_line(f"Echo: {command}")
```

### Command Processor Handler

```python
from chuk_protocol_server.handlers.line_handler import LineHandler

class CommandHandler(LineHandler):
    def __init__(self, reader, writer):
        super().__init__(reader, writer)
        self.commands = {
            "help": self.cmd_help,
            "status": self.cmd_status,
            "uptime": self.cmd_uptime
        }
    
    async def process_line(self, line: str) -> bool:
        if not line.strip():
            await self.show_prompt()
            return True
            
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in ["quit", "exit"]:
            await self.end_session("Goodbye!")
            return False
            
        if cmd in self.commands:
            await self.commands[cmd](args)
        else:
            await self.send_line(f"Unknown command: {cmd}")
            
        await self.show_prompt()
        return True
    
    async def cmd_help(self, args):
        await self.send_line("Available commands: help, status, uptime, quit")
    
    async def cmd_status(self, args):
        await self.send_line("Server status: OK")
    
    async def cmd_uptime(self, args):
        await self.send_line("Server uptime: 3 days, 4 hours")
```

## Terminal Handling

The framework includes sophisticated terminal handling that correctly negotiates capabilities with telnet clients:

1. **Initial Negotiation**: Establishes proper terminal settings at connection time
2. **Visual Feedback**: Echoes characters and provides appropriate visual feedback
3. **Control Character Handling**: Properly processes CR, LF, backspace, and other control characters
4. **Window Size**: Adapts to client terminal dimensions when available
5. **Terminal Type**: Detects client terminal type for specialized behavior

## Session Monitoring

For WebSocket servers, you can enable session monitoring to observe client interactions:

```yaml
websocket:
  # ... other options ...
  enable_monitoring: true
  monitor_path: "/monitor"
```

Connect to the monitoring endpoint with a WebSocket client:

```javascript
// Monitor all sessions
const monitor = new WebSocket('ws://localhost:8025/monitor');
monitor.onmessage = function(event) {
  const data = JSON.parse(event.data);
  console.log('Session event:', data);
};

// Watch a specific session
monitor.send(JSON.stringify({
  type: 'watch_session',
  session_id: 'SESSION_ID'
}));
```

## Extending the Framework

### Adding a New Transport

1. Create a new server class extending `BaseServer`
2. Implement required methods for your transport
3. Add the transport type to the server launcher

### Creating Custom Handlers

1. Extend one of the base handler classes (BaseHandler, CharacterHandler, LineHandler, TelnetHandler)
2. Implement your application logic
3. Configure the server to use your handler

## Logging

The framework includes comprehensive logging to assist with debugging:

```python
# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Different components use different loggers:
- `chuk-protocol-server`: Main logger for server events
- `base-server`: Server lifecycle events
- `character-handler`: Character processing events
- `websocket-adapter`: WebSocket connection events
- `ws-plain-server`: WebSocket server events

## Performance Considerations

- The server uses asyncio for efficient handling of multiple connections
- Character-by-character processing is more CPU-intensive than line mode
- Connection cleanup is handled carefully to prevent resource leaks
- WebSocket connections include ping/pong frames to detect disconnects

## Troubleshooting

Common issues and solutions:

- **^M characters visible**: Check that proper terminal negotiations are being sent
- **No character echo**: Verify ECHO option negotiation
- **Slow performance**: Reduce logging level in production environments
- **Connection resets**: Ensure proper error handling in custom handlers
- **WebSocket client doesn't exit**: Use the `--exit-on-eof` flag with websocat

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[MIT License](LICENSE)

## Acknowledgements

- Telnet protocol specifications (RFCs 854, 855, 856, etc.)
- The asyncio library for elegant async/await support
- The websockets library for WebSocket protocol support
- The Python community for inspiration and feedback