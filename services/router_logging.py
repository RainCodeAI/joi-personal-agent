from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime

LOG_PATH = Path("./data/router_logs.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


def log_inference(entry: Dict[str, Any]) -> None:
    """Append a router inference record to the log file."""
    record = {"ts": datetime.utcnow().isoformat(), **entry}
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def get_recent_logs(limit: int = 50) -> List[Dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-limit:]
    return [json.loads(line) for line in reversed(recent)]
