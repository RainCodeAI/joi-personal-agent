"""Joi Desktop Tray Application (Phase 10).

System tray launcher that:
- Starts the Streamlit server in the background
- Provides a tray icon with menu (Open, Restart, Quit)
- Registers a global hotkey (Ctrl+Space) to toggle the browser window
- Sends native Windows notifications for proactive messages
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

# Resolve paths relative to this file
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

APP_ENTRY = os.path.join(BASE_DIR, "app", "ui", "App.py")
STREAMLIT_PORT = int(os.environ.get("JOI_PORT", "8501"))
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"

# Icon path (fallback to None if missing)
ICON_PATH = os.path.join(BASE_DIR, "static", "assets", "joi_icon.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = None


class JoiTrayApp:
    """Manages the Streamlit subprocess and system tray icon."""

    def __init__(self):
        self._server_proc = None
        self._tray_icon = None

    # ── Streamlit Server ──────────────────────────────────────────────────

    def start_server(self):
        """Launch Streamlit as a subprocess."""
        if self._server_proc and self._server_proc.poll() is None:
            log.info("Server already running.")
            return

        if getattr(sys, 'frozen', False):
            # Frozen mode: Call ourselves with a flag to act as the streamlit runner
            cmd = [
                sys.executable,
                "--run-streamlit",
                APP_ENTRY,
                "--server.port", str(STREAMLIT_PORT),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ]
        else:
            # Dev mode: Standard python -m streamlit
            cmd = [
                sys.executable, "-m", "streamlit", "run", APP_ENTRY,
                "--server.port", str(STREAMLIT_PORT),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
            ]

        log.info(f"Starting Streamlit: {' '.join(cmd)}")
        self._server_proc = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            stdout=sys.stdout,  # Pipe directly to console
            stderr=sys.stderr,  # Pipe directly to console
            # Remove CREATE_NO_WINDOW so we can see output if needed, 
            # or keep it but ensure stdout/err goes to the parent terminal.
            # Since the user has a terminal open via StartJoi.bat, inheriting handles works best.
            creationflags=0, 
        )
        log.info(f"Streamlit PID: {self._server_proc.pid}")

    def stop_server(self):
        """Gracefully stop the Streamlit subprocess."""
        if self._server_proc and self._server_proc.poll() is None:
            log.info("Stopping Streamlit server...")
            if sys.platform == "win32":
                self._server_proc.terminate()
            else:
                self._server_proc.send_signal(signal.SIGTERM)
            self._server_proc.wait(timeout=10)
            log.info("Server stopped.")

    def restart_server(self):
        self.stop_server()
        self.start_server()

    # ── Browser ───────────────────────────────────────────────────────────

    def open_browser(self):
        """Open or focus the Joi browser tab."""
        webbrowser.open(STREAMLIT_URL)

    # ── System Tray ───────────────────────────────────────────────────────

    def run_tray(self):
        """Start the system tray icon (blocking)."""
        try:
            import pystray
            from PIL import Image as PILImage
        except ImportError:
            log.error("pystray or Pillow not installed. Run: pip install pystray Pillow")
            log.info("Running without tray icon — server only.")
            self.start_server()
            self._server_proc.wait()
            return

        # Create icon image
        if ICON_PATH:
            icon_image = PILImage.open(ICON_PATH)
        else:
            # Generate a simple cyan square as fallback icon
            icon_image = PILImage.new("RGB", (64, 64), color=(0, 243, 255))

        menu = pystray.Menu(
            pystray.MenuItem("Open Joi", lambda: self.open_browser(), default=True),
            pystray.MenuItem("Restart Server", lambda: self.restart_server()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.quit()),
        )

        self._tray_icon = pystray.Icon("Joi", icon_image, "Joi - Personal Agent", menu)

        # Start server before showing tray
        self.start_server()
        
        # Auto-open browser on launch (UX improvement)
        self.open_browser()

        # Start global hotkey listener in background
        hotkey_thread = threading.Thread(target=self._register_hotkey, daemon=True)
        hotkey_thread.start()

        log.info("Tray icon running. Right-click for menu.")
        self._tray_icon.run()

    def quit(self):
        """Shut down everything."""
        self.stop_server()
        if self._tray_icon:
            self._tray_icon.stop()

    # ── Global Hotkey (Phase 10.2) ────────────────────────────────────────

    def _register_hotkey(self):
        """Register Ctrl+Space as a global hotkey to toggle Joi."""
        try:
            import keyboard
            keyboard.add_hotkey("ctrl+space", self.open_browser)
            log.info("Global hotkey registered: Ctrl+Space")
            keyboard.wait()  # Block this thread
        except ImportError:
            log.warning("keyboard package not installed. Global hotkey disabled.")
        except Exception as e:
            log.warning(f"Could not register hotkey: {e}")


# ── Native Notifications (Phase 10.2) ────────────────────────────────────

def send_notification(title: str, message: str):
    """Send a native OS notification.

    Uses win10toast on Windows, plyer as cross-platform fallback.
    """
    if sys.platform == "win32":
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(
                title, message,
                icon_path=ICON_PATH,
                duration=5,
                threaded=True,
            )
            return
        except ImportError:
            pass

    # Cross-platform fallback
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Joi",
            timeout=5,
        )
    except ImportError:
        log.warning("No notification backend available. Install win10toast or plyer.")


def run_streamlit_subprocess():
    """Entry point for the frozen subprocess."""
    from streamlit.web import cli as stcli
    # Remove the --run-streamlit flag
    if "--run-streamlit" in sys.argv:
        sys.argv.remove("--run-streamlit")
    
    # sys.argv is now ['Joi.exe', 'app/ui/App.py', '--server.port', ...]
    # Streamlit expects ['streamlit', 'run', 'app/ui/App.py', ...]
    # We construct the equivalent argument list for stcli.main()
    
    # Actually stcli.main uses sys.argv directly or can take args.
    # It parses "streamlit run script.py".
    # We need to simulate: "streamlit run app/ui/App.py ..."
    
    # Argument 0 is the script name (or exe).
    # We want: ["streamlit", "run", APP_ENTRY, ...]
    
    # Let's clean up sys.argv to match `streamlit run ...`
    # Our cmd in start_server was: [exe, "--run-streamlit", APP_ENTRY, args...]
    # So sys.argv here is [exe, APP_ENTRY, args...]
    
    # We need to insert "run" at index 1?
    # No, stcli.main() typically expects arguments as if called from command line.
    # if we call `stcli.main()`, it looks at `sys.argv`.
    # Standard call: `streamlit run app.py` -> sys.argv=['streamlit', 'run', 'app.py']
    
    new_argv = ["streamlit", "run"] + sys.argv[1:]
    sys.argv = new_argv
    sys.exit(stcli.main())


def main():
    if getattr(sys, 'frozen', False) and "--run-streamlit" in sys.argv:
        run_streamlit_subprocess()
        return

    app = JoiTrayApp()
    app.run_tray()


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    main()
