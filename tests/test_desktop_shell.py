from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

from desktop import tray_app, window_shell


def test_window_state_round_trip_and_coercion(tmp_path: Path) -> None:
    path = tmp_path / "desktop_shell.json"
    window_shell.save_window_state(
        path,
        {
            "width": 1600,
            "height": 900,
            "x": 20,
            "y": 30,
            "always_on_top": True,
            "start_minimized": False,
        },
    )

    state = window_shell.load_window_state(path)

    assert json.loads(path.read_text(encoding="utf-8"))["width"] == 1600
    assert state["always_on_top"] is True
    assert window_shell.coerce_dimension("500", 1280, minimum=900, maximum=3840) == 900
    assert window_shell.coerce_position("42") == 42
    assert window_shell.coerce_position("invalid") is None


def test_conflicting_window_flags_are_rejected() -> None:
    assert window_shell.main(["--always-on-top", "--no-always-on-top"]) == 2
    assert window_shell.main(["--start-minimized", "--no-start-minimized"]) == 2


def test_start_minimized_does_not_require_pywebview(tmp_path: Path) -> None:
    config = tmp_path / "desktop_shell.json"

    result = window_shell.main(
        [
            "--config",
            str(config),
            "--start-minimized",
            "--no-browser-fallback",
        ]
    )

    assert result == 0
    assert window_shell.load_window_state(config)["start_minimized"] is True


def test_dispatch_browser_event_uses_native_shell_source() -> None:
    scripts: list[str] = []
    window = SimpleNamespace(evaluate_js=scripts.append)

    window_shell.dispatch_browser_event(window, window_shell.VOICE_PTT_START_EVENT)

    assert len(scripts) == 1
    assert window_shell.VOICE_PTT_START_EVENT in scripts[0]
    assert "native-shell" in scripts[0]


def test_native_capture_api_updates_title_and_tray(monkeypatch) -> None:
    titles: list[str] = []
    commands: list[tuple[int, str]] = []
    api = window_shell.NativeShellApi()
    api.window = SimpleNamespace(set_title=titles.append)
    monkeypatch.setattr(
        window_shell,
        "send_command",
        lambda port, command: commands.append((port, command)) or True,
    )

    assert api.set_capture_active(True) is True
    assert api.set_capture_active(False) is True

    assert titles == ["Joi - Screen capture active", "Joi"]
    assert commands == [
        (window_shell.TRAY_CONTROL_PORT, "capture_start"),
        (window_shell.TRAY_CONTROL_PORT, "capture_end"),
    ]


def test_screen_capture_event_dispatches_to_browser() -> None:
    scripts: list[str] = []
    window = SimpleNamespace(evaluate_js=scripts.append)

    window_shell.dispatch_browser_event(window, window_shell.SCREEN_CAPTURE_EVENT)

    assert window_shell.SCREEN_CAPTURE_EVENT in scripts[0]


def test_voice_hotkey_dispatches_once_per_press_and_stops_after_modifier_release(
    monkeypatch,
) -> None:
    callbacks: dict[str, object] = {}
    pressed = {"ctrl": True, "shift": True, "alt": False}

    class FakeKeyboard:
        @staticmethod
        def is_pressed(key: str) -> bool:
            return pressed.get(key, False)

        @staticmethod
        def on_press_key(key: str, callback, suppress: bool = False) -> None:
            callbacks[f"press:{key}"] = callback

        @staticmethod
        def on_release_key(key: str, callback, suppress: bool = False) -> None:
            callbacks[f"release:{key}"] = callback

        @staticmethod
        def unhook(callback) -> None:
            pass

    class FakeEvent:
        def __init__(self) -> None:
            self.handlers = []

        def __iadd__(self, handler):
            self.handlers.append(handler)
            return self

    events = SimpleNamespace(closing=FakeEvent())
    window = SimpleNamespace(events=events)
    dispatched: list[str] = []
    monkeypatch.setitem(sys.modules, "keyboard", FakeKeyboard)
    monkeypatch.setattr(
        window_shell,
        "dispatch_browser_event",
        lambda _window, event_name: dispatched.append(event_name),
    )

    window_shell.register_voice_hotkey(window)
    press = callbacks["press:space"]
    release = callbacks["release:space"]

    press(None)
    press(None)
    pressed["ctrl"] = False
    pressed["shift"] = False
    release(None)

    assert dispatched == [
        window_shell.VOICE_PTT_START_EVENT,
        window_shell.VOICE_PTT_STOP_EVENT,
    ]
    assert len(events.closing.handlers) == 1


def test_tray_capture_commands_update_visible_status(monkeypatch) -> None:
    app = tray_app.JoiTrayApp.__new__(tray_app.JoiTrayApp)
    app._capture_active = False
    refreshes: list[bool] = []
    monkeypatch.setattr(app, "_update_icon", lambda: refreshes.append(app._capture_active))

    assert app._handle_control_command("capture_start") is True
    assert app.status_text() == "Status: screen capture active"
    assert app._handle_control_command("capture_end") is True

    assert app._capture_active is False
    assert refreshes == [True, False]


def test_tray_screen_hotkey_focuses_window_and_dispatches(monkeypatch) -> None:
    app = tray_app.JoiTrayApp.__new__(tray_app.JoiTrayApp)
    opened: list[bool] = []
    commands: list[tuple[int, str]] = []
    monkeypatch.setattr(app, "open_joi", lambda: opened.append(True))
    monkeypatch.setattr(
        tray_app,
        "send_command",
        lambda port, command: commands.append((port, command)) or True,
    )

    app._trigger_screen_capture()

    assert opened == [True]
    assert commands == [(tray_app.WINDOW_CONTROL_PORT, "look_at_this")]
