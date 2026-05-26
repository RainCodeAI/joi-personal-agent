"""Native desktop window shell for the Joi web UI.

This is intentionally thin: the existing Next.js app remains the UI, while
pywebview gives it native window behavior for the desktop launcher.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any

log = logging.getLogger("joi.window")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if getattr(sys, "frozen", False):
    BASE_DIR = Path(getattr(sys, "_MEIPASS")).resolve()
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG_PATH = BASE_DIR / "data" / "desktop_shell.json"
DEFAULT_URL = os.environ.get("JOI_APP_URL", "http://localhost:3000")
DEFAULT_API_URL = os.environ.get("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
VOICE_PTT_START_EVENT = "joi:native-ptt-start"
VOICE_PTT_STOP_EVENT = "joi:native-ptt-stop"

DEFAULT_WINDOW_STATE: dict[str, Any] = {
    "width": 1280,
    "height": 860,
    "x": None,
    "y": None,
    "always_on_top": False,
    "start_minimized": False,
}


def load_window_state(path: Path) -> dict[str, Any]:
    state = DEFAULT_WINDOW_STATE.copy()
    try:
        if path.exists():
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update({key: loaded.get(key, state[key]) for key in state})
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read desktop shell state from %s: %s", path, exc)
    return state


def save_window_state(path: Path, state: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not save desktop shell state to %s: %s", path, exc)


def coerce_dimension(value: Any, fallback: int, *, minimum: int, maximum: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, coerced))


def coerce_position(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def open_browser_fallback(url: str) -> None:
    log.info("Opening Joi in the default browser: %s", url)
    webbrowser.open(url)


def dispatch_browser_event(window: Any, event_name: str) -> None:
    script = (
        "window.dispatchEvent(new CustomEvent("
        f"{json.dumps(event_name)}, "
        "{ detail: { source: 'native-shell' } }"
        "));"
    )
    try:
        window.evaluate_js(script)
    except Exception as exc:
        log.debug("Could not dispatch %s to the web UI: %s", event_name, exc)


def register_voice_hotkey(window: Any) -> None:
    try:
        import keyboard
    except ImportError:
        log.warning("keyboard package not installed. Native push-to-talk hotkey disabled.")
        return

    active = False

    def modifiers_pressed() -> bool:
        return (
            keyboard.is_pressed("ctrl")
            and keyboard.is_pressed("shift")
            and not keyboard.is_pressed("alt")
        )

    def on_space_press(_: Any) -> None:
        nonlocal active
        if active or not modifiers_pressed():
            return
        active = True
        dispatch_browser_event(window, VOICE_PTT_START_EVENT)

    def on_space_release(_: Any) -> None:
        nonlocal active
        if not active:
            return
        active = False
        dispatch_browser_event(window, VOICE_PTT_STOP_EVENT)

    def clear_hotkeys(*_: Any) -> None:
        try:
            keyboard.unhook(on_space_press)
            keyboard.unhook(on_space_release)
        except Exception:
            pass

    try:
        keyboard.on_press_key("space", on_space_press, suppress=False)
        keyboard.on_release_key("space", on_space_release, suppress=False)
        if getattr(window, "events", None) is not None:
            window.events.closing += clear_hotkeys
        log.info("Native push-to-talk registered: Ctrl+Shift+Space")
    except Exception as exc:
        log.warning("Could not register native push-to-talk hotkey: %s", exc)


def launch_window(
    *,
    url: str,
    config_path: Path,
    always_on_top: bool | None,
    start_minimized: bool | None,
    browser_fallback: bool,
    voice_hotkey: bool,
) -> int:
    state = load_window_state(config_path)
    if always_on_top is not None:
        state["always_on_top"] = always_on_top
    if start_minimized is not None:
        state["start_minimized"] = start_minimized

    if state.get("start_minimized"):
        save_window_state(config_path, state)
        log.info("Desktop shell is configured to start minimized; no window opened.")
        return 0

    try:
        import webview
    except ImportError:
        message = "pywebview is not installed. Install pywebview to use the native desktop shell."
        if browser_fallback:
            log.warning("%s Falling back to browser.", message)
            open_browser_fallback(url)
            return 0
        log.error(message)
        return 2

    width = coerce_dimension(state.get("width"), 1280, minimum=900, maximum=3840)
    height = coerce_dimension(state.get("height"), 860, minimum=640, maximum=2160)
    x = coerce_position(state.get("x"))
    y = coerce_position(state.get("y"))

    window_kwargs: dict[str, Any] = {
        "width": width,
        "height": height,
        "resizable": True,
        "min_size": (900, 640),
        "on_top": bool(state.get("always_on_top")),
    }
    if x is not None:
        window_kwargs["x"] = x
    if y is not None:
        window_kwargs["y"] = y

    window = webview.create_window("Joi", url, **window_kwargs)

    def persist_current_window(*_: Any) -> None:
        next_state = load_window_state(config_path)
        for attr in ("width", "height", "x", "y"):
            value = getattr(window, attr, None)
            if value is not None:
                next_state[attr] = value
        next_state["always_on_top"] = bool(state.get("always_on_top"))
        next_state["start_minimized"] = bool(state.get("start_minimized"))
        save_window_state(config_path, next_state)

    for event_name in ("resized", "moved", "closing"):
        event = getattr(window.events, event_name, None)
        if event is not None:
            try:
                event += persist_current_window
            except Exception as exc:
                log.debug("Could not bind %s event: %s", event_name, exc)

    def on_started() -> None:
        if voice_hotkey:
            register_voice_hotkey(window)

    log.info("Opening Joi desktop shell: %s", url)
    webview.start(on_started, debug=False)
    persist_current_window()
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open Joi in a native desktop window.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Joi frontend URL to load.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Local Joi API URL for child environment.")
    parser.add_argument("--token", default=os.environ.get("JOI_API_TOKEN", ""), help="Local Joi API token.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Window state JSON path.")
    parser.add_argument("--always-on-top", action="store_true", help="Open the window above other windows.")
    parser.add_argument("--no-always-on-top", action="store_true", help="Disable the persisted always-on-top setting.")
    parser.add_argument("--start-minimized", action="store_true", help="Persist start-minimized mode and do not open a window.")
    parser.add_argument("--no-start-minimized", action="store_true", help="Disable the persisted start-minimized setting.")
    parser.add_argument("--disable-voice-hotkey", action="store_true", help="Disable native Ctrl+Shift+Space push-to-talk.")
    parser.add_argument("--no-browser-fallback", action="store_true", help="Fail instead of opening a browser when pywebview is missing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    os.environ["JOI_API_TOKEN"] = args.token
    os.environ["NEXT_PUBLIC_JOI_API_TOKEN"] = args.token
    os.environ["NEXT_PUBLIC_API_BASE_URL"] = args.api_url
    os.environ["API_BASE_URL"] = args.api_url
    os.environ["JOI_APP_URL"] = args.url

    always_on_top = None
    if args.always_on_top:
        always_on_top = True
    if args.no_always_on_top:
        always_on_top = False

    start_minimized = None
    if args.start_minimized:
        start_minimized = True
    if args.no_start_minimized:
        start_minimized = False

    return launch_window(
        url=args.url,
        config_path=Path(args.config),
        always_on_top=always_on_top,
        start_minimized=start_minimized,
        browser_fallback=not args.no_browser_fallback,
        voice_hotkey=not args.disable_voice_hotkey,
    )


if __name__ == "__main__":
    raise SystemExit(main())
