from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.config import settings


class RuntimeSettingsStore:
    """Persist a small mutable subset of backend settings for API clients."""

    _allowed_keys = {
        "airgap",
        "autonomy_level",
        "enable_proactive_messaging",
        "model_chat",
        "model_embed",
        "router_timeout",
        "gguf_n_ctx",
        "gguf_n_gpu_layers",
    }

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/runtime_settings.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._overrides = self._load()
        self._apply_overrides()

    def get(self) -> Dict[str, Any]:
        values = {key: getattr(settings, key) for key in sorted(self._allowed_keys)}
        return values

    def update(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in patch.items():
            if key not in self._allowed_keys:
                raise KeyError(key)
            setattr(settings, key, value)
            self._overrides[key] = value
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
        self.path.write_text(json.dumps(self._overrides, indent=2, sort_keys=True))

    def _apply_overrides(self) -> None:
        for key, value in self._overrides.items():
            if key in self._allowed_keys:
                setattr(settings, key, value)
