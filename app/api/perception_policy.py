from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class PerceptionPolicyStore:
    """Persist user-controlled perception and privacy policy settings."""

    _defaults: Dict[str, Any] = {
        "camera_enabled": True,
        "screen_access": "disabled",
        "retain_expressions": False,
        "retain_snapshots": False,
        "retention_days": 0,
    }

    _allowed_keys = set(_defaults.keys())

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/perception_policy.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._policy = {**self._defaults, **self._load()}

    def get(self) -> Dict[str, Any]:
        return {**self._policy}

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in patch.items():
            if key not in self._allowed_keys:
                raise KeyError(key)
            if key == "screen_access" and value not in {"disabled", "manual_only"}:
                raise ValueError("screen_access must be 'disabled' or 'manual_only'")
            self._policy[key] = value
        self._policy["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._persist()
        return self.get()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text())
        except Exception:
            return {}

    def _persist(self) -> None:
        self.path.write_text(json.dumps(self._policy, indent=2, sort_keys=True))
