"""Phase 10 initiative quality gate.

Sits between candidate construction and the existing policy gate:

    candidate builder -> quality gate -> policy gate -> emit/suppress

It judges whether an *evidence-bound* (context-triggered) candidate references
something real, arrives at a plausible moment, and isn't repetitive, before the
policy gate applies quiet hours / DND / limits. Timer-driven candidates carry no
evidence and bypass this gate entirely — their recurrence is intentional.

Scoring is deterministic (no LLM): per the spec's non-goals, initiative text
must stay evidence-bound, so the gate never generates language, it only scores
and can hard-suppress. A safety score below the floor suppresses regardless of
the weighted total.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.initiative.emission_memory import InitiativeEmissionMemory
from app.initiative.policy import CandidateEvidence, InitiativeCandidate

# Weights and thresholds from docs/initiative_quality_gate_spec.md.
WEIGHTS = {
    "relevance": 0.30,
    "timing": 0.20,
    "recency": 0.15,
    "novelty": 0.20,
    "safety": 0.15,
}
DEFAULT_THRESHOLD = 0.75
SAFETY_FLOOR = 0.70
NOVELTY_WINDOW_DAYS = 7

# Minimum characters for an excerpt to count as concrete rather than generic.
_MIN_EXCERPT_CHARS = 20

# Attributable source types the gate recognizes as grounded evidence.
_GROUNDED_SOURCE_TYPES = {
    "memory",
    "synthesis_record",
    "user_model",
    "project",
    "mood_log",
    "context_event",
}

# Language that implies a diagnosis, personality judgment, relationship read, or
# prediction — the spec forbids these outright, so they crush the safety score.
_UNSAFE_MARKERS = (
    "you have depression",
    "you're depressed",
    "you are depressed",
    "you have anxiety",
    "you're anxious because",
    "diagnos",
    "you always",
    "you never",
    "you clearly",
    "the real reason you",
    "you obviously",
    "narcissi",
    "bipolar",
    "you're going to fail",
    "you will fail",
    "your relationship",
    "you don't really love",
)

# Recency sweet spot (hours): too fresh and the user still remembers; too stale
# and a follow-up feels random. Mirrors build_memory_followup_candidate's window.
_RECENCY_MIN_HOURS = 2.0
_RECENCY_MAX_HOURS = 72.0


@dataclass(frozen=True)
class QualityScore:
    initiative_type: str
    total: float
    relevance: float
    timing: float
    recency: float
    novelty: float
    safety: float
    threshold: float
    decision: str  # "pass" | "suppress"
    topic_key: str | None = None
    hard_reason: str | None = None

    @property
    def passed(self) -> bool:
        return self.decision == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "initiative_type": self.initiative_type,
            "total": self.total,
            "relevance": self.relevance,
            "timing": self.timing,
            "recency": self.recency,
            "novelty": self.novelty,
            "safety": self.safety,
            "threshold": self.threshold,
            "decision": self.decision,
            "topic_key": self.topic_key,
            "hard_reason": self.hard_reason,
        }


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class InitiativeQualityGate:
    """Deterministic pre-policy quality gate for evidence-bound initiatives."""

    def __init__(
        self,
        memory: InitiativeEmissionMemory | None = None,
        *,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._memory = memory
        self._threshold = threshold
        self._recent: list[dict[str, Any]] = []

    def evaluate(
        self,
        candidate: InitiativeCandidate,
        *,
        now: datetime | None = None,
    ) -> QualityScore:
        current = now or datetime.now(timezone.utc)
        evidence = candidate.evidence
        topic_key = self._topic_key(candidate, evidence)

        hard_reason = self._hard_suppression(candidate, evidence, topic_key, current)

        relevance = self._score_relevance(evidence)
        timing = self._score_timing(candidate)
        recency = self._score_recency(evidence, current)
        novelty = 0.0 if (topic_key and self._seen_recently(topic_key, current)) else 1.0
        safety = self._score_safety(candidate, evidence)

        total = round(
            WEIGHTS["relevance"] * relevance
            + WEIGHTS["timing"] * timing
            + WEIGHTS["recency"] * recency
            + WEIGHTS["novelty"] * novelty
            + WEIGHTS["safety"] * safety,
            4,
        )

        if hard_reason is not None:
            decision = "suppress"
        elif safety < SAFETY_FLOOR:
            decision = "suppress"
            hard_reason = "safety below floor"
        elif total < self._threshold:
            decision = "suppress"
            hard_reason = "below quality threshold"
        else:
            decision = "pass"

        score = QualityScore(
            initiative_type=candidate.type,
            total=total,
            relevance=round(relevance, 4),
            timing=round(timing, 4),
            recency=round(recency, 4),
            novelty=round(novelty, 4),
            safety=round(safety, 4),
            threshold=self._threshold,
            decision=decision,
            topic_key=topic_key,
            hard_reason=hard_reason,
        )
        self._remember(candidate, score)
        return score

    def record_emission(
        self,
        candidate: InitiativeCandidate,
        score: QualityScore,
        *,
        now: datetime | None = None,
    ) -> None:
        """Persist an emitted evidence-bound initiative for repeat suppression."""
        if self._memory is None or not score.topic_key:
            return
        source_ids = []
        if candidate.evidence and candidate.evidence.source_id:
            source_ids.append(candidate.evidence.source_id)
        self._memory.record(
            initiative_type=candidate.type,
            topic_key=score.topic_key,
            message=candidate.message,
            quality_score=score.total,
            session_id=candidate.session_id,
            source_ids=source_ids,
            emitted_at=now,
        )

    def register_feedback(
        self, session_id: str, *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Resolve pending initiative feedback for a session on a user reply."""
        if self._memory is None:
            return []
        return self._memory.register_user_reply(session_id, now=now)

    def recent_decisions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._recent[-max(1, limit):][::-1]

    def recent_emissions(self, *, limit: int = 20) -> list[dict[str, Any]]:
        if self._memory is None:
            return []
        return self._memory.recent(limit=limit)

    # ── scoring dimensions ────────────────────────────────────────────────

    @staticmethod
    def _score_relevance(evidence: CandidateEvidence | None) -> float:
        if evidence is None:
            return 0.0
        excerpt = (evidence.excerpt or "").strip()
        if len(excerpt) < _MIN_EXCERPT_CHARS:
            return 0.2
        grounded = evidence.source_type in _GROUNDED_SOURCE_TYPES
        attributable = bool(evidence.source_id)
        if grounded and attributable:
            return 1.0
        if grounded or attributable:
            return 0.7
        return 0.4

    @staticmethod
    def _score_timing(candidate: InitiativeCandidate) -> float:
        # The policy gate is authoritative for quiet hours / presence; here we
        # only reward candidates that haven't already expired.
        expires = _parse_dt(candidate.expires_at)
        if expires is None:
            return 0.8
        return 0.8 if datetime.now(timezone.utc) <= expires else 0.2

    @staticmethod
    def _score_recency(evidence: CandidateEvidence | None, now: datetime) -> float:
        if evidence is None:
            return 0.0
        observed = _parse_dt(evidence.observed_at)
        if observed is None:
            return 0.5  # undated evidence: neutral, neither fresh nor stale
        age_hours = (now - observed).total_seconds() / 3600
        if age_hours < 0:
            return 0.3
        if age_hours < _RECENCY_MIN_HOURS:
            return 0.4  # too fresh — the user still has it in mind
        if age_hours <= _RECENCY_MAX_HOURS:
            return 1.0
        # Decay past the window rather than a hard cliff.
        overage = age_hours - _RECENCY_MAX_HOURS
        return max(0.2, 1.0 - overage / _RECENCY_MAX_HOURS)

    @staticmethod
    def _score_safety(
        candidate: InitiativeCandidate, evidence: CandidateEvidence | None
    ) -> float:
        haystack = candidate.message.lower()
        if evidence and evidence.excerpt:
            haystack += " " + evidence.excerpt.lower()
        for marker in _UNSAFE_MARKERS:
            if marker in haystack:
                return 0.0
        return 1.0

    # ── hard suppression ──────────────────────────────────────────────────

    def _hard_suppression(
        self,
        candidate: InitiativeCandidate,
        evidence: CandidateEvidence | None,
        topic_key: str | None,
        now: datetime,
    ) -> str | None:
        if evidence is None:
            return "no evidence"
        excerpt = (evidence.excerpt or "").strip()
        if len(excerpt) < _MIN_EXCERPT_CHARS:
            return "evidence too generic"
        if evidence.source_type not in _GROUNDED_SOURCE_TYPES and not evidence.source_id:
            return "evidence not attributable"
        if topic_key and self._seen_recently(topic_key, now):
            return f"similar initiative within {NOVELTY_WINDOW_DAYS}d"
        return None

    def _seen_recently(self, topic_key: str, now: datetime) -> bool:
        if self._memory is None:
            return False
        return self._memory.seen_topic_within(
            topic_key, since_days=NOVELTY_WINDOW_DAYS, now=now
        )

    @staticmethod
    def _topic_key(
        candidate: InitiativeCandidate, evidence: CandidateEvidence | None
    ) -> str | None:
        if evidence is None:
            return None
        if evidence.topic_key:
            return evidence.topic_key
        if evidence.source_id:
            return f"{candidate.type}:{evidence.source_type}:{evidence.source_id}"
        return None

    def _remember(self, candidate: InitiativeCandidate, score: QualityScore) -> None:
        self._recent.append(
            {
                "candidate": candidate.to_dict(),
                "quality_score": score.to_dict(),
            }
        )
        if len(self._recent) > 50:
            self._recent = self._recent[-50:]
