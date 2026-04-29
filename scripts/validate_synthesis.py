from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.user_model.synthesis import SynthesisCandidate, extract_candidates


@dataclass(frozen=True)
class CuratedSession:
    name: str
    messages: list[str]
    expected_sections: set[str]


CURATED_SESSIONS = [
    CuratedSession(
        name="project_goal_worry",
        messages=[
            "I'm building the user model diagnostics page tonight.",
            "My goal is to make Joi's memory feel trustworthy before we enable inference.",
            "I'm worried about storing the wrong thing and making her feel less careful.",
            "I still haven't written the review checklist for synthesis output.",
        ],
        expected_sections={
            "active_projects",
            "stated_goals",
            "recurring_worries",
            "open_loops",
        },
    ),
    CuratedSession(
        name="people_preferences_win",
        messages=[
            "My friend Sarah helped me think through the hardware node.",
            "Can you just be more direct when you're giving me implementation options?",
            "I finally got the MQTT bridge working after a few rough attempts.",
            "Feeling good about the direction tonight.",
        ],
        expected_sections={
            "important_people",
            "communication_preferences",
            "recent_wins",
            "mood_trend",
        },
    ),
    CuratedSession(
        name="open_loop_and_duplicate_shape",
        messages=[
            "I've been working on a FastAPI backend for Joi.",
            "I need to follow up with Dana about the ESP32 LED behavior.",
            "Dana is my colleague from the hardware side.",
            "I completed the prompt preview panel.",
        ],
        expected_sections={
            "active_projects",
            "open_loops",
            "important_people",
            "recent_wins",
        },
    ),
    CuratedSession(
        name="small_talk_negative_control",
        messages=[
            "Hi Joi.",
            "It's good to hear from you too. I've just been hanging around today.",
            "Nothing important, just taking it slow.",
        ],
        expected_sections=set(),
    ),
]


def _message(content: str, role: str = "user") -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content, session_id="validation", timestamp=None)


def _summarize_candidates(candidates: Iterable[SynthesisCandidate]) -> list[dict]:
    return [
        {
            "section": candidate.section_key,
            "label": candidate.label,
            "confidence": candidate.confidence,
            "skipped": candidate.blocked_by_correction or candidate.duplicate_of_existing,
            "duplicate": candidate.duplicate_of_existing,
            "blocked": candidate.blocked_by_correction,
            "excerpt": candidate.source_excerpt,
        }
        for candidate in candidates
    ]


def run_curated() -> list[dict]:
    reports = []
    for session in CURATED_SESSIONS:
        messages = [_message(content) for content in session.messages]
        candidates = extract_candidates(messages, include_skipped=True)
        sections = {candidate.section_key for candidate in candidates}
        reports.append(
            {
                "name": session.name,
                "message_count": len(messages),
                "expected_sections": sorted(session.expected_sections),
                "actual_sections": sorted(sections),
                "missing_sections": sorted(session.expected_sections - sections),
                "extra_sections": sorted(sections - session.expected_sections),
                "candidates": _summarize_candidates(candidates),
            }
        )
    return reports


def run_real_db(db_path: Path, limit: int) -> list[dict]:
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        sessions = conn.execute(
            """
            select s.id, s.title, s.updated_at, count(m.id) as message_count
            from chatsession s
            join chatmessage m on m.session_id = s.id
            group by s.id
            order by s.updated_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()

        reports = []
        for session in sessions:
            rows = conn.execute(
                """
                select role, content, timestamp
                from chatmessage
                where session_id = ?
                order by timestamp, id
                """,
                (session["id"],),
            ).fetchall()
            messages = [
                SimpleNamespace(
                    role=row["role"],
                    content=row["content"],
                    session_id=session["id"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]
            candidates = extract_candidates(messages, include_skipped=True)
            reports.append(
                {
                    "id": session["id"],
                    "title": session["title"],
                    "updated_at": session["updated_at"],
                    "message_count": session["message_count"],
                    "candidate_count": len(candidates),
                    "candidates": _summarize_candidates(candidates),
                }
            )
        return reports
    finally:
        conn.close()


def print_text_report(curated: list[dict], real: list[dict]) -> None:
    print("Curated synthesis validation")
    print("=" * 30)
    for report in curated:
        status = "ok" if not report["missing_sections"] and not report["extra_sections"] else "check"
        print(f"\n[{status}] {report['name']} ({report['message_count']} messages)")
        print(f"  expected: {', '.join(report['expected_sections']) or '-'}")
        print(f"  actual:   {', '.join(report['actual_sections']) or '-'}")
        if report["missing_sections"]:
            print(f"  missing:  {', '.join(report['missing_sections'])}")
        if report["extra_sections"]:
            print(f"  extra:    {', '.join(report['extra_sections'])}")
        for candidate in report["candidates"]:
            marker = " skipped" if candidate["skipped"] else ""
            print(
                f"  - {candidate['section']}: {candidate['label']} "
                f"({candidate['confidence']:.2f}{marker})"
            )

    if not real:
        return

    print("\nReal DB dry-run sample")
    print("=" * 22)
    for report in real:
        print(
            f"\n{report['id']} - {report['message_count']} messages, "
            f"{report['candidate_count']} candidates"
        )
        for candidate in report["candidates"]:
            marker = " skipped" if candidate["skipped"] else ""
            print(
                f"  - {candidate['section']}: {candidate['label']} "
                f"({candidate['confidence']:.2f}{marker})"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run user-model synthesis against curated sessions and optional real DB sessions.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--real-db", action="store_true", help="Also sample real sessions from data/agent.db.")
    parser.add_argument("--db-path", default="data/agent.db", help="SQLite database path for --real-db.")
    parser.add_argument("--limit", type=int, default=5, help="Number of real DB sessions to sample.")
    args = parser.parse_args()

    curated = run_curated()
    real = run_real_db(ROOT / args.db_path, args.limit) if args.real_db else []
    if args.json:
        print(json.dumps({"curated": curated, "real": real}, indent=2, ensure_ascii=False))
    else:
        print_text_report(curated, real)

    has_curated_mismatch = any(
        report["missing_sections"] or report["extra_sections"]
        for report in curated
    )
    return 1 if has_curated_mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
