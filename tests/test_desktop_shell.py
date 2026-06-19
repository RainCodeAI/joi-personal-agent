from __future__ import annotations

import json
from pathlib import Path

from desktop import window_shell


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
