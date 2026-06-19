from __future__ import annotations

import socket

from desktop.local_control import LocalControlServer, send_command


def test_local_control_server_dispatches_commands() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    commands: list[str] = []
    server = LocalControlServer(port, lambda command: not commands.append(command))
    server.start()
    try:
        assert send_command(port, "show") is True
        assert commands == ["show"]
    finally:
        server.stop()
