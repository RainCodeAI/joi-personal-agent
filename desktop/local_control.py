from __future__ import annotations

import json
import socket
import socketserver
import threading
from collections.abc import Callable
from typing import Any


TRAY_CONTROL_PORT = 48721
WINDOW_CONTROL_PORT = 48722


def send_command(port: int, command: str, timeout: float = 0.75) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
            client.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))
            response = client.recv(1024).decode("utf-8").strip()
            return response == "ok"
    except OSError:
        return False


class _ControlHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            payload = json.loads(self.rfile.readline(4096).decode("utf-8"))
            command = str(payload.get("command") or "")
            accepted = bool(self.server.command_handler(command))  # type: ignore[attr-defined]
        except Exception:
            accepted = False
        self.wfile.write(b"ok\n" if accepted else b"error\n")


class LocalControlServer:
    def __init__(self, port: int, handler: Callable[[str], bool]) -> None:
        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server: Any = Server(("127.0.0.1", port), _ControlHandler)
        self._server.command_handler = handler
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"joi-control-{port}",
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
