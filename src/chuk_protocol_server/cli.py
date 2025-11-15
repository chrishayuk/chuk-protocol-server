"""
Main CLI entry point for chuk-protocol-server
Provides a convenient dispatcher for all server commands
"""
import sys
import argparse


def main():
    """Main CLI dispatcher for chuk-protocol-server commands."""
    parser = argparse.ArgumentParser(
        prog="chuk-protocol-server",
        description="A production-ready protocol library for TCP, WebSocket, and Telnet servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available commands:
  guess-who-server          Launch the Guess Who game server
  echo-server              Launch the Echo server
  sample-server            Launch any sample server or custom config
  server-launcher          Low-level server launcher

Examples:
  # Quick launch sample servers
  chuk-protocol-server guess-who-server
  chuk-protocol-server echo-server

  # Launch sample servers by name
  chuk-protocol-server sample-server guess_who_server
  chuk-protocol-server sample-server echo_server

  # Launch with custom config
  chuk-protocol-server sample-server -c /path/to/config.yaml

  # List available sample servers
  chuk-protocol-server sample-server --list

  # Low-level launcher with options
  chuk-protocol-server server-launcher -c config.yaml -vv

For more information, visit: https://github.com/chrishayuk/chuk-protocol-server
        """
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run (guess-who-server, echo-server, sample-server, server-launcher)"
    )

    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the command"
    )

    # Parse arguments
    args = parser.parse_args()

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Dispatch to appropriate command
    command = args.command.lower()

    if command == "guess-who-server":
        from chuk_protocol_server.guess_who_launcher import main as guess_who_main
        sys.argv = ["guess-who-server"] + args.args
        guess_who_main()

    elif command == "echo-server":
        from chuk_protocol_server.echo_launcher import main as echo_main
        sys.argv = ["echo-server"] + args.args
        echo_main()

    elif command == "sample-server":
        from chuk_protocol_server.sample_server_launcher import main as sample_main
        sys.argv = ["sample-server"] + args.args
        sample_main()

    elif command == "server-launcher":
        from chuk_protocol_server.server_launcher import main as server_main
        sys.argv = ["server-launcher"] + args.args
        server_main()

    else:
        print(f"Error: Unknown command '{args.command}'", file=sys.stderr)
        print("\nAvailable commands: guess-who-server, echo-server, sample-server, server-launcher", file=sys.stderr)
        print("Run 'chuk-protocol-server --help' for more information.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
