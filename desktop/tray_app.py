"""Joi desktop tray launcher for the FastAPI + Next.js stack."""

from __future__ import annotations

import atexit
import json
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
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_STANDARD_STREAM_FALLBACKS = []


def _ensure_standard_streams() -> None:
    """Windowed PyInstaller builds can start with stdout/stderr set to None."""

    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is not None:
            continue
        stream = open(os.devnull, "w", encoding="utf-8", buffering=1)
        _STANDARD_STREAM_FALLBACKS.append(stream)
        setattr(sys, name, stream)


_ensure_standard_streams()

try:
    from desktop.local_control import (
        LocalControlServer,
        TRAY_CONTROL_PORT,
        WINDOW_CONTROL_PORT,
        send_command,
    )
except ModuleNotFoundError:
    from local_control import (
        LocalControlServer,
        TRAY_CONTROL_PORT,
        WINDOW_CONTROL_PORT,
        send_command,
    )

log = logging.getLogger("joi.tray")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
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
WATCHDOG_INTERVAL_SECONDS = 5
WATCHDOG_WINDOW_SECONDS = 300
WATCHDOG_MAX_RESTARTS = 3

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
        self._desired_running = False
        self._lock = threading.RLock()
        self._control_server: LocalControlServer | None = None
        self._watchdog_thread: threading.Thread | None = None
        self._capture_active = False
        self._camera_active = False
        self._camera_policy_enabled_cache: bool | None = None
        self._restart_history: dict[str, deque[float]] = {
            "api": deque(),
            "frontend": deque(),
        }
        atexit.register(self.stop_stack)

    def _child_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["JOI_API_TOKEN"] = self._token
        env["NEXT_PUBLIC_JOI_API_TOKEN"] = self._token
        env["NEXT_PUBLIC_API_BASE_URL"] = API_URL
        env["API_BASE_URL"] = API_URL
        env["HOSTNAME"] = WEB_HOST
        env["PORT"] = str(WEB_PORT)
        env["JOI_NATIVE_NOTIFICATIONS"] = "1"
        if FROZEN:
            env["JOI_DATA_DIR"] = str(
                Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Joi" / "data"
            )
        else:
            env["JOI_DATA_DIR"] = str(BASE_DIR / "data")
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
        if self._capture_active:
            return "Status: screen capture active"
        if self._camera_active:
            return "Status: camera active"
        camera_enabled = self._camera_policy_enabled()
        if camera_enabled is False:
            return "Status: camera suspended"
        if self.stack_running():
            return "Status: running"
        if self.api_running() or self.frontend_running():
            return "Status: partial"
        return "Status: stopped"

    def start_api(self) -> None:
        with self._lock:
            if self.api_running():
                return
            if FROZEN:
                cmd = [sys.executable, "--api-server"]
            else:
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
            if FROZEN:
                node = BASE_DIR / ("node.exe" if sys.platform == "win32" else "node")
                server = FRONTEND_DIR / "server.js"
                if not node.exists() or not server.exists():
                    missing = [str(path) for path in (node, server) if not path.exists()]
                    raise RuntimeError(
                        "Packaged frontend runtime is incomplete; missing: " + ", ".join(missing)
                    )
                cmd = [str(node), str(server)]
            else:
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
        self._desired_running = True
        try:
            self.start_api()
            self.start_frontend()
        except Exception:
            log.exception("Joi stack startup failed")
            self.stop_stack()
            return
        self._start_watchdog()
        threading.Thread(target=self._wait_for_stack_and_open, daemon=True).start()

    def stop_stack(self) -> None:
        self._desired_running = False
        self._capture_active = False
        self._camera_active = False
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
                send_command(WINDOW_CONTROL_PORT, "show")
                return
            self._state.window = None
            if FROZEN:
                cmd = [sys.executable, "--window-shell"]
            else:
                shell_path = BASE_DIR / "desktop" / "window_shell.py"
                cmd = [sys.executable, str(shell_path)]
            cmd.extend([
                "--url",
                APP_URL,
                "--api-url",
                API_URL,
                "--token",
                self._token,
            ])
            if always_on_top:
                cmd.append("--always-on-top")
            if not respect_start_minimized:
                cmd.append("--no-start-minimized")
            self._state.window = self._popen_detached(cmd, cwd=BASE_DIR, env=self._child_env())

    def hide_joi(self) -> None:
        if not send_command(WINDOW_CONTROL_PORT, "hide"):
            log.info("Joi desktop window is not open.")

    def close_window(self) -> None:
        with self._lock:
            graceful = send_command(WINDOW_CONTROL_PORT, "quit")
            if graceful and self._process_running(self._state.window):
                try:
                    assert self._state.window is not None
                    self._state.window.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            self._terminate_process_tree(self._state.window, "desktop window")
            self._state.window = None

    def _start_watchdog(self) -> None:
        if self._watchdog_thread is not None and self._watchdog_thread.is_alive():
            return
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="joi-watchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def _restart_allowed(self, name: str) -> bool:
        now = time.monotonic()
        history = self._restart_history[name]
        while history and now - history[0] > WATCHDOG_WINDOW_SECONDS:
            history.popleft()
        if len(history) >= WATCHDOG_MAX_RESTARTS:
            return False
        history.append(now)
        return True

    def _watchdog_loop(self) -> None:
        while not self._closing:
            time.sleep(WATCHDOG_INTERVAL_SECONDS)
            if not self._desired_running:
                continue
            for name, starter in (("api", self.start_api), ("frontend", self.start_frontend)):
                proc = getattr(self._state, "web" if name == "frontend" else name)
                if self._process_running(proc):
                    continue
                if not self._restart_allowed(name):
                    log.error(
                        "%s restart limit reached (%d attempts in %ds)",
                        name,
                        WATCHDOG_MAX_RESTARTS,
                        WATCHDOG_WINDOW_SECONDS,
                    )
                    self._desired_running = False
                    self._update_icon()
                    break
                log.warning("%s process exited unexpectedly; restarting", name)
                try:
                    starter()
                except Exception as exc:
                    log.error("%s watchdog restart failed: %s", name, exc)

    def _handle_control_command(self, command: str) -> bool:
        if command in {"capture_start", "capture_end"}:
            self._capture_active = command == "capture_start"
            self._update_icon()
            return True
        if command in {"camera_start", "camera_end"}:
            self._camera_active = command == "camera_start"
            self._update_icon()
            return True
        if command in {"show", "focus"}:
            self.open_joi()
            return True
        if command == "hide":
            self.hide_joi()
            return True
        if command == "quit":
            threading.Thread(target=self.quit, daemon=True).start()
            return True
        return False

    def _api_json(self, path: str, *, method: str = "GET", payload: dict | None = None) -> dict | None:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"{API_URL}{path}", data=body, method=method)
        request.add_header("X-Joi-Api-Token", self._token)
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                if response.status < 200 or response.status >= 300:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            log.debug("Perception policy request failed: %s", exc)
            return None

    def _camera_policy_enabled(self) -> bool | None:
        if not self.api_running():
            return self._camera_policy_enabled_cache
        payload = self._api_json("/api/v2/perception/policy")
        policy = payload.get("policy") if isinstance(payload, dict) else None
        if isinstance(policy, dict) and isinstance(policy.get("camera_enabled"), bool):
            self._camera_policy_enabled_cache = policy["camera_enabled"]
        return self._camera_policy_enabled_cache

    def _camera_status_text(self) -> str:
        if self._camera_active:
            return "Camera: active"
        camera_enabled = self._camera_policy_enabled()
        if camera_enabled is False:
            return "Camera: suspended"
        if camera_enabled is True:
            return "Camera: enabled"
        return "Camera: unknown"

    def _set_camera_enabled(self, enabled: bool) -> None:
        if not self.api_running():
            log.warning("Cannot update camera policy because the API is not running.")
            return
        payload = self._api_json(
            "/api/v2/perception/policy",
            method="PATCH",
            payload={"camera_enabled": enabled},
        )
        policy = payload.get("policy") if isinstance(payload, dict) else None
        if isinstance(policy, dict) and isinstance(policy.get("camera_enabled"), bool):
            self._camera_policy_enabled_cache = policy["camera_enabled"]
            if not policy["camera_enabled"]:
                self._camera_active = False
        self._update_icon()

    def suspend_camera(self) -> None:
        self._set_camera_enabled(False)

    def resume_camera(self) -> None:
        self._set_camera_enabled(True)

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
            self._control_server = LocalControlServer(TRAY_CONTROL_PORT, self._handle_control_command)
            self._control_server.start()
        except OSError as exc:
            log.error("Another Joi tray instance may already be running: %s", exc)
            return

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
            pystray.MenuItem(lambda _: self._camera_status_text(), None, enabled=False),
            pystray.MenuItem("Open Joi Window", lambda _icon, _item: self.open_joi(), default=True),
            pystray.MenuItem("Hide Joi Window", lambda _icon, _item: self.hide_joi()),
            pystray.MenuItem("Open Always On Top", lambda _icon, _item: self.open_joi(always_on_top=True)),
            pystray.MenuItem("Open in Browser", lambda _icon, _item: self.open_browser()),
            pystray.MenuItem(
                "Suspend Camera",
                lambda _icon, _item: self.suspend_camera(),
                enabled=lambda _: self.api_running() and self._camera_policy_enabled() is not False,
            ),
            pystray.MenuItem(
                "Resume Camera",
                lambda _icon, _item: self.resume_camera(),
                enabled=lambda _: self.api_running() and self._camera_policy_enabled() is False,
            ),
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
        if self._control_server:
            self._control_server.stop()
            self._control_server = None
        if self._tray_icon:
            self._tray_icon.stop()

    def _register_hotkey(self) -> None:
        try:
            import keyboard

            keyboard.add_hotkey("ctrl+space", self.open_joi)
            keyboard.add_hotkey("ctrl+shift+l", self._trigger_screen_capture)
            log.info("Global hotkey registered: Ctrl+Space")
            log.info("Global screen capture hotkey registered: Ctrl+Shift+L")
            keyboard.wait()
        except ImportError:
            log.warning("keyboard package not installed. Global hotkey disabled.")
        except Exception as exc:
            log.warning("Could not register hotkey: %s", exc)

    def _trigger_screen_capture(self) -> None:
        self.open_joi()
        for _ in range(15):
            if send_command(WINDOW_CONTROL_PORT, "look_at_this"):
                return
            time.sleep(0.2)
        log.warning("Could not deliver screen capture hotkey to the Joi window.")


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


def run_api_server() -> None:
    import uvicorn

    uvicorn.run("app.api.main:app", host=API_HOST, port=API_PORT)


def main() -> None:
    if "--window-shell" in sys.argv:
        from desktop import window_shell

        args = [arg for arg in sys.argv[1:] if arg != "--window-shell"]
        raise SystemExit(window_shell.main(args))
    if "--api-server" in sys.argv:
        run_api_server()
        return
    if send_command(TRAY_CONTROL_PORT, "show"):
        log.info("Joi is already running; focused the existing instance.")
        return

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
