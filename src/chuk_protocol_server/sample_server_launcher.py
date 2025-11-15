"""
Sample Server Launcher
Generic launcher for sample servers included with chuk-protocol-server.
"""
import sys
import argparse
from pathlib import Path
from chuk_protocol_server.server_launcher import main as server_launcher_main


def get_available_servers():
    """Get a list of available sample servers."""
    package_dir = Path(__file__).parent
    sample_servers_dir = package_dir / "sample_servers"

    if not sample_servers_dir.exists():
        return []

    servers = []
    for item in sample_servers_dir.iterdir():
        if item.is_dir() and not item.name.startswith('__'):
            config_path = item / "config.yaml"
            if config_path.exists():
                servers.append(item.name)

    return sorted(servers)


def launch_sample_server(server_name: str):
    """Launch a sample server by name."""
    package_dir = Path(__file__).parent
    config_path = package_dir / "sample_servers" / server_name / "config.yaml"

    if not config_path.exists():
        available = get_available_servers()
        print(f"Error: Server '{server_name}' not found.", file=sys.stderr)
        print(f"\nAvailable sample servers:", file=sys.stderr)
        for srv in available:
            print(f"  - {srv}", file=sys.stderr)
        sys.exit(1)

    # Set up arguments as if they were passed via command line
    sys.argv = ["sample-server", "-c", str(config_path)]

    # Launch the server
    server_launcher_main()


def main():
    """Main entry point for the sample server launcher."""
    parser = argparse.ArgumentParser(
        description="Launch a sample server from the chuk-protocol-server package or a custom config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch a built-in sample server
  sample-server echo_server
  sample-server guess_who_server

  # Launch with a custom config file
  sample-server -c /path/to/config.yaml
  sample-server --config ./my_server/config.yaml

  # List available sample servers
  sample-server --list
        """
    )

    parser.add_argument(
        "server_name",
        nargs="?",
        help="Name of the sample server to launch (if not using --config)"
    )

    parser.add_argument(
        "-c", "--config",
        help="Path to a custom configuration file"
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available sample servers"
    )

    args = parser.parse_args()

    # Handle list option
    if args.list:
        available = get_available_servers()
        print("Available sample servers:")
        for srv in available:
            print(f"  - {srv}")
        return

    # Handle custom config file
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"Error: Configuration file not found at {config_path}", file=sys.stderr)
            sys.exit(1)

        # Set up arguments and launch
        sys.argv = ["sample-server", "-c", str(config_path)]
        server_launcher_main()
        return

    # Require server name if not listing or using custom config
    if not args.server_name:
        parser.error("server_name is required (or use --config for custom config, or --list to see available servers)")

    # Launch the requested sample server
    launch_sample_server(args.server_name)


if __name__ == "__main__":
    main()
