"""
Guess Who Server Launcher
Convenience launcher for the Guess Who game server.
"""
from chuk_protocol_server.sample_server_launcher import launch_sample_server


def main():
    """Launch the Guess Who server with its default configuration."""
    launch_sample_server("guess_who_server")


if __name__ == "__main__":
    main()
