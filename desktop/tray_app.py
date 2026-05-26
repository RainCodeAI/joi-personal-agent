"""Joi desktop tray launcher for the FastAPI + Next.js stack."""

from __future__ import annotations

import atexit
import logging
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger("joi.tray")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS")).resolve()
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

FRONTEND_DIR = BASE_DIR / "frontend"
ENV_PATH = BASE_DIR / ".env"

API_HOST = "127.0.0.1"
WEB_HOST = "127.0.0.1"
API_PORT = int(os.environ.get("JOI_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("JOI_WEB_PORT", "3000"))
API_URL = f"http://{API_HOST}:{API_PORT}"
APP_URL = f"http://localhost:{WEB_PORT}"
HEALTH_URL = f"{API_URL}/health"

ICON_PATH = BASE_DIR / "static" / "assets" / "joi_icon.ico"
if not ICON_PATH.exists():
    ICON_PATH = None


@dataclass
class ProcessState:
    api: Optional[subprocess.Popen] = None
    web: Optional[subprocess.Popen] = None
    window: Optional[subprocess.Popen] = None


def _read_env_value(key: str) -> str:
    if not ENV_PATH.exists():
        return ""
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def _ensure_api_token() -> str:
    token = os.environ.get("JOI_API_TOKEN") or _read_env_value("JOI_API_TOKEN")
    if not token or token.startswith("change-me"):
        token = secrets.token_urlsafe(32)
        log.info("Generated in-memory Joi API token for this desktop session")
    os.environ["JOI_API_TOKEN"] = token
    os.environ["NEXT_PUBLIC_JOI_API_TOKEN"] = token
    return token


def _startupinfo():
    if sys.platform != "win32":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def _creationflags() -> int:
    if sys.platform != "win32":
        return 0
    return subprocess.CREATE_NEW_PROCESS_GROUP


def _url_ok(url: str, *, token: str = "", timeout: float = 1.5) -> bool:
    request = urllib.request.Request(url)
    if token:
        request.add_header("X-Joi-Api-Token", token)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError):
        return False


class JoiTrayApp:
    """Manages Joi's local API and web UI processes."""

    def __init__(self) -> None:
        self._token = _ensure_api_token()
        self._state = ProcessState()
        self._tray_icon = None
        self._closing = False
        self._lock = threading.RLock()
        atexit.register(self.stop_stack)

    def _child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["JOI_API_TOKEN"] = self._token
        env["NEXT_PUBLIC_JOI_API_TOKEN"] = self._token
        env["NEXT_PUBLIC_API_BASE_URL"] = API_URL
        env["API_BASE_URL"] = API_URL
        env["HOSTNAME"] = WEB_HOST
        env["PORT"] = str(WEB_PORT)
        return env

    def _popen(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen:
        log.info("Starting: %s", " ".join(cmd))
        return subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            startupinfo=_startupinfo(),
            creationflags=_creationflags(),
        )

    def _popen_detached(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen:
        log.info("Starting: %s", " ".join(cmd))
        return subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            startupinfo=_startupinfo(),
            creationflags=_creationflags(),
        )

    def _process_running(self, proc: Optional[subprocess.Popen]) -> bool:
        return proc is not None and proc.poll() is None

    def api_running(self) -> bool:
        return self._process_running(self._state.api)

    def frontend_running(self) -> bool:
        return self._process_running(self._state.web)

    def stack_running(self) -> bool:
        return self.api_running() and self.frontend_running()

    def status_text(self) -> str:
        if self.stack_running():
            return "Status: running"
        if self.api_running() or self.frontend_running():
            return "Status: partial"
        return "Status: stopped"

    def start_api(self) -> None:
        with self._lock:
            if self.api_running():
                return
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "app.api.main:app",
                "--host",
                API_HOST,
                "--port",
                str(API_PORT),
            ]
            self._state.api = self._popen(cmd, cwd=BASE_DIR, env=self._child_env())
            log.info("API PID: %d", self._state.api.pid)
            self._update_icon()

    def start_frontend(self) -> None:
        with self._lock:
            if self.frontend_running():
                return
            npm = "npm.cmd" if sys.platform == "win32" else "npm"
            cmd = [npm, "run", "dev", "--", "--hostname", WEB_HOST, "--port", str(WEB_PORT)]
            self._state.web = self._popen(cmd, cwd=FRONTEND_DIR, env=self._child_env())
            log.info("Frontend PID: %d", self._state.web.pid)
            self._update_icon()

    def _terminate_process_tree(self, proc: Optional[subprocess.Popen], name: str) -> None:
        if not self._process_running(proc):
            return
        assert proc is not None
        log.info("Stopping %s PID %d", name, proc.pid)
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def stop_api(self) -> None:
        with self._lock:
            self._terminate_process_tree(self._state.api, "API")
            self._state.api = None
            self._update_icon()

    def stop_frontend(self) -> None:
        with self._lock:
            self._terminate_process_tree(self._state.web, "frontend")
            self._state.web = None
            self._update_icon()

    def start_stack(self) -> None:
        self.start_api()
        self.start_frontend()
        threading.Thread(target=self._wait_for_stack_and_open, daemon=True).start()

    def stop_stack(self) -> None:
        self.close_window()
        self.stop_frontend()
        self.stop_api()

    def restart_stack(self) -> None:
        self.stop_stack()
        self.start_stack()

    def _wait_for_stack_and_open(self) -> None:
        api_ready = self._wait_for_url(HEALTH_URL, token=self._token, label="API", timeout_seconds=60)
        web_ready = self._wait_for_url(APP_URL, label="frontend", timeout_seconds=90)
        self._update_icon()
        if api_ready and web_ready and not self._closing:
            self.open_joi(respect_start_minimized=True)
        else:
            log.warning("Joi stack did not become fully ready: api=%s frontend=%s", api_ready, web_ready)

    def _wait_for_url(self, url: str, *, label: str, token: str = "", timeout_seconds: int = 60) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline and not self._closing:
            if _url_ok(url, token=token):
                log.info("%s is ready", label)
                return True
            time.sleep(1)
        return False

    def open_browser(self) -> None:
        webbrowser.open(APP_URL)

    def open_joi(self, *, always_on_top: bool = False, respect_start_minimized: bool = False) -> None:
        with self._lock:
            if self._process_running(self._state.window):
                return
            shell_path = BASE_DIR / "desktop" / "window_shell.py"
            cmd = [
                sys.executable,
                str(shell_path),
                "--url",
                APP_URL,
                "--api-url",
                API_URL,
                "--token",
                self._token,
            ]
            if always_on_top:
                cmd.append("--always-on-top")
            if not respect_start_minimized:
                cmd.append("--no-start-minimized")
            self._state.window = self._popen_detached(cmd, cwd=BASE_DIR, env=self._child_env())

    def close_window(self) -> None:
        with self._lock:
            self._terminate_process_tree(self._state.window, "desktop window")
            self._state.window = None

    def _update_icon(self) -> None:
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.title = f"Joi - {self.status_text().removeprefix('Status: ')}"
            self._tray_icon.update_menu()
        except Exception as exc:
            log.debug("Tray refresh failed: %s", exc)

    def run_tray(self) -> None:
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            log.error("pystray or Pillow not installed. Run: pip install pystray Pillow")
            log.info("Running without tray icon.")
            self.start_stack()
            if self._state.api:
                self._state.api.wait()
            return

        icon_image = PILImage.open(ICON_PATH) if ICON_PATH else PILImage.new("RGB", (64, 64), color=(0, 243, 255))

        menu = pystray.Menu(
            pystray.MenuItem(lambda _: self.status_text(), None, enabled=False),
            pystray.MenuItem("Open Joi Window", lambda _icon, _item: self.open_joi(), default=True),
            pystray.MenuItem("Open Always On Top", lambda _icon, _item: self.open_joi(always_on_top=True)),
            pystray.MenuItem("Open in Browser", lambda _icon, _item: self.open_browser()),
            pystray.MenuItem(
                "Start Joi",
                lambda _icon, _item: self.start_stack(),
                enabled=lambda _: not self.stack_running(),
            ),
            pystray.MenuItem(
                "Stop Joi",
                lambda _icon, _item: self.stop_stack(),
                enabled=lambda _: self.api_running() or self.frontend_running(),
            ),
            pystray.MenuItem("Restart Joi", lambda _icon, _item: self.restart_stack()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda _icon, _item: self.quit()),
        )

        self._tray_icon = pystray.Icon("Joi", icon_image, "Joi - starting", menu)
        self.start_stack()

        hotkey_thread = threading.Thread(target=self._register_hotkey, daemon=True)
        hotkey_thread.start()

        log.info("Tray icon running. Right-click for menu.")
        self._tray_icon.run()

    def quit(self) -> None:
        self._closing = True
        self.stop_stack()
        if self._tray_icon:
            self._tray_icon.stop()

    def _register_hotkey(self) -> None:
        try:
            import keyboard

            keyboard.add_hotkey("ctrl+space", self.open_joi)
            log.info("Global hotkey registered: Ctrl+Space")
            keyboard.wait()
        except ImportError:
            log.warning("keyboard package not installed. Global hotkey disabled.")
        except Exception as exc:
            log.warning("Could not register hotkey: %s", exc)


def send_notification(title: str, message: str) -> None:
    if sys.platform == "win32":
        try:
            from win10toast import ToastNotifier

            ToastNotifier().show_toast(
                title,
                message,
                icon_path=str(ICON_PATH) if ICON_PATH else None,
                duration=5,
                threaded=True,
            )
            return
        except ImportError:
            pass
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="Joi", timeout=5)
    except ImportError:
        log.warning("No notification backend available. Install win10toast or plyer.")


def main() -> None:
    app = JoiTrayApp()
    if "--check" in sys.argv:
        print(app.status_text())
        app.stop_stack()
        return
    app.run_tray()


if __name__ == "__main__":
    from multiprocessing import freeze_support

    freeze_support()
    main()
