"""AuditLogger — Structured decision-trace logging for the Joi orchestrator.

Writes one JSON object per orchestrator call to ``data/agent_traces.jsonl``.
The Diagnostics page reads this file to render the Agent Traces table.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

TRACE_FILE = Path("data/agent_traces.jsonl")


@dataclass
class DecisionTrace:
    """One orchestrator invocation trace."""

    timestamp: str
    session_id: str
    sub_agents_invoked: List[str]
    context_summary: str          # first ~200 chars of assembled context
    llm_prompt_hash: str          # SHA-256 of the full prompt (privacy-safe)
    llm_response_preview: str     # first ~200 chars of the LLM response
    tool_calls: List[Dict[str, Any]]
    threats_detected: List[str]
    latency_ms: int


class AuditLogger:
    """Append-only JSONL logger for agent decision traces."""

    def __init__(self, path: Path = TRACE_FILE) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log_decision_trace(
        self,
        session_id: str,
        sub_agents_invoked: List[str],
        context_summary: str,
        llm_response_preview: str,
        tool_calls: List[Dict[str, Any]],
        threats_detected: List[str],
        latency_ms: int,
        llm_prompt: Optional[str] = None,
    ) -> DecisionTrace:
        """Create and persist a decision trace.  Returns the trace object."""
        prompt_hash = (
            hashlib.sha256(llm_prompt.encode()).hexdigest()[:16]
            if llm_prompt
            else "n/a"
        )

        trace = DecisionTrace(
            timestamp=datetime.utcnow().isoformat(),
            session_id=session_id,
            sub_agents_invoked=sub_agents_invoked,
            context_summary=context_summary[:200],
            llm_prompt_hash=prompt_hash,
            llm_response_preview=llm_response_preview[:200],
            tool_calls=tool_calls,
            threats_detected=threats_detected,
            latency_ms=latency_ms,
        )

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                json.dump(asdict(trace), f)
                f.write("\n")
        except Exception as exc:
            log.warning("Failed to write decision trace: %s", exc)

        return trace

    def read_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Read the most recent *limit* traces (newest first)."""
        if not self._path.exists():
            return []

        traces: List[Dict[str, Any]] = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        traces.append(json.loads(line))
        except Exception as exc:
            log.warning("Failed to read traces: %s", exc)

        # Return newest first, capped
        return list(reversed(traces[-limit:]))
