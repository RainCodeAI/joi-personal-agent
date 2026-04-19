"""Joi Desktop Tray Application — v2 stack launcher.

Starts the FastAPI backend and Next.js frontend as subprocesses, provides a
system tray icon with Open / Restart / Quit, and registers a global hotkey
(Ctrl+Space) to open the browser window.
"""

import os
import sys
import signal
import subprocess
import threading
import webbrowser
import logging

log = logging.getLogger("joi.tray")
logging.basicConfig(level=logging.INFO)

if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

API_PORT = int(os.environ.get("JOI_API_PORT", "8000"))
WEB_PORT = int(os.environ.get("JOI_WEB_PORT", "3000"))
APP_URL = f"http://localhost:{WEB_PORT}"

ICON_PATH = os.path.join(BASE_DIR, "static", "assets", "joi_icon.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = None


class JoiTrayApp:
    """Manages the FastAPI + Next.js subprocesses and the system tray icon."""

    def __init__(self):
        self._api_proc = None
        self._web_proc = None
        self._tray_icon = None

    # ── Backend (FastAPI) ─────────────────────────────────────────────────

    def start_api(self):
        if self._api_proc and self._api_proc.poll() is None:
            return
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.api.main:app",
            "--host", "127.0.0.1",
            "--port", str(API_PORT),
        ]
        log.info("Starting API: %s", " ".join(cmd))
        self._api_proc = subprocess.Popen(cmd, cwd=BASE_DIR)
        log.info("API PID: %d", self._api_proc.pid)

    def stop_api(self):
        if self._api_proc and self._api_proc.poll() is None:
            log.info("Stopping API server…")
            if sys.platform == "win32":
                self._api_proc.terminate()
            else:
                self._api_proc.send_signal(signal.SIGTERM)
            try:
                self._api_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._api_proc.kill()

    # ── Frontend (Next.js) ────────────────────────────────────────────────

    def start_frontend(self):
        if self._web_proc and self._web_proc.poll() is None:
            return

        # Production: `next start` (requires a prior `npm run build`)
        # Falls back to dev mode if .next/standalone doesn't exist yet
        standalone = os.path.join(FRONTEND_DIR, ".next", "standalone")
        if os.path.isdir(standalone):
            cmd = ["node", "server.js"]
            cwd = standalone
            env = {**os.environ, "PORT": str(WEB_PORT), "HOSTNAME": "127.0.0.1"}
        else:
            log.warning("No production build found — starting Next.js in dev mode")
            npm = "npm.cmd" if sys.platform == "win32" else "npm"
            cmd = [npm, "run", "dev", "--", "--port", str(WEB_PORT)]
            cwd = FRONTEND_DIR
            env = os.environ.copy()

        log.info("Starting frontend: %s", " ".join(cmd))
        self._web_proc = subprocess.Popen(cmd, cwd=cwd, env=env)
        log.info("Frontend PID: %d", self._web_proc.pid)

    def stop_frontend(self):
        if self._web_proc and self._web_proc.poll() is None:
            log.info("Stopping frontend…")
            if sys.platform == "win32":
                self._web_proc.terminate()
            else:
                self._web_proc.send_signal(signal.SIGTERM)
            try:
                self._web_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._web_proc.kill()

    # ── Combined ──────────────────────────────────────────────────────────

    def start_stack(self):
        self.start_api()
        self.start_frontend()

    def stop_stack(self):
        self.stop_frontend()
        self.stop_api()

    def restart_stack(self):
        self.stop_stack()
        self.start_stack()

    # ── Browser ───────────────────────────────────────────────────────────

    def open_browser(self):
        webbrowser.open(APP_URL)

    # ── System Tray ───────────────────────────────────────────────────────

    def run_tray(self):
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            log.error("pystray or Pillow not installed. Run: pip install pystray Pillow")
            log.info("Running without tray icon — stack only.")
            self.start_stack()
            self._api_proc.wait()
            return

        if ICON_PATH:
            icon_image = PILImage.open(ICON_PATH)
        else:
            icon_image = PILImage.new("RGB", (64, 64), color=(0, 243, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Open Joi", lambda: self.open_browser(), default=True),
            pystray.MenuItem("Restart Stack", lambda: self.restart_stack()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.quit()),
        )

        self._tray_icon = pystray.Icon("Joi", icon_image, "Joi — Personal Agent", menu)

        self.start_stack()
        # Give the API a moment to bind before opening the browser
        threading.Timer(2.5, self.open_browser).start()

        hotkey_thread = threading.Thread(target=self._register_hotkey, daemon=True)
        hotkey_thread.start()

        log.info("Tray icon running. Right-click for menu.")
        self._tray_icon.run()

    def quit(self):
        self.stop_stack()
        if self._tray_icon:
            self._tray_icon.stop()

    # ── Global Hotkey ─────────────────────────────────────────────────────

    def _register_hotkey(self):
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+space", self.open_browser)
            log.info("Global hotkey registered: Ctrl+Space")
            keyboard.wait()
        except ImportError:
            log.warning("keyboard package not installed. Global hotkey disabled.")
        except Exception as e:
            log.warning("Could not register hotkey: %s", e)


# ── Native Notifications ──────────────────────────────────────────────────

def send_notification(title: str, message: str):
    if sys.platform == "win32":
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, message, icon_path=ICON_PATH, duration=5, threaded=True)
            return
        except ImportError:
            pass
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="Joi", timeout=5)
    except ImportError:
        log.warning("No notification backend available. Install win10toast or plyer.")


def main():
    app = JoiTrayApp()
    app.run_tray()


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    main()
