from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.user_model.synthesis import SynthesisCandidate, extract_candidates
from app.user_model.llm_synthesis import build_llm_synthesis_prompt, parse_llm_candidates


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


def _load_llm_fixture(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    fixture_path = Path(path)
    if not fixture_path.is_absolute():
        fixture_path = ROOT / fixture_path
    with fixture_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload if isinstance(payload, dict) else {}


def _fixture_response(fixtures: dict[str, Any], group: str, key: str) -> str | None:
    group_payload = fixtures.get(group)
    if isinstance(group_payload, dict) and key in group_payload:
        value = group_payload[key]
    elif key in fixtures:
        value = fixtures[key]
    else:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _run_live_llm(messages: list[Any], *, session_key: str, group: str) -> dict[str, Any]:
    from services.ai_router import route_request

    prompt = build_llm_synthesis_prompt(messages)
    routed = route_request(
        prompt,
        {
            "task": "user_model_synthesis_validation",
            "session_key": session_key,
            "group": group,
            "dry_run": True,
            "writes_enabled": False,
        },
    )
    return {
        "raw_response": str(routed.get("response") or ""),
        "provider": {
            "selected": str(routed.get("model_used") or ""),
            "route": list(routed.get("route") or []),
            "errors": list(routed.get("errors") or []),
        },
    }


def _llm_report(
    messages: list[Any],
    *,
    session_key: str,
    group: str,
    fixtures: dict[str, Any] | None = None,
    live: bool = False,
) -> dict[str, Any] | None:
    raw_response = _fixture_response(fixtures or {}, group, session_key)
    source = "fixture" if raw_response is not None else ""
    provider: dict[str, Any] = {}
    if raw_response is None and live:
        live_response = _run_live_llm(messages, session_key=session_key, group=group)
        raw_response = live_response["raw_response"]
        provider = live_response["provider"]
        source = "live"
    if raw_response is None:
        return None

    candidates = parse_llm_candidates(
        raw_response,
        messages,
        include_skipped=True,
    )
    return {
        "source": source,
        "provider": provider,
        "sections": sorted({candidate.section_key for candidate in candidates}),
        "candidate_count": len(candidates),
        "candidates": _summarize_candidates(candidates),
    }


def _section_delta(regex_sections: set[str], llm_sections: set[str]) -> dict[str, list[str]]:
    return {
        "shared": sorted(regex_sections & llm_sections),
        "regex_only": sorted(regex_sections - llm_sections),
        "llm_only": sorted(llm_sections - regex_sections),
    }


def run_curated(
    *,
    llm_fixtures: dict[str, Any] | None = None,
    llm_live: bool = False,
) -> list[dict]:
    reports = []
    for session in CURATED_SESSIONS:
        messages = [_message(content) for content in session.messages]
        regex_candidates = extract_candidates(messages, include_skipped=True)
        regex_sections = {candidate.section_key for candidate in regex_candidates}
        llm = _llm_report(
            messages,
            session_key=session.name,
            group="curated",
            fixtures=llm_fixtures,
            live=llm_live,
        )
        llm_sections = set(llm["sections"]) if llm else set()
        reports.append(
            {
                "name": session.name,
                "message_count": len(messages),
                "expected_sections": sorted(session.expected_sections),
                "actual_sections": sorted(regex_sections),
                "missing_sections": sorted(session.expected_sections - regex_sections),
                "extra_sections": sorted(regex_sections - session.expected_sections),
                "candidates": _summarize_candidates(regex_candidates),
                "regex": {
                    "sections": sorted(regex_sections),
                    "candidate_count": len(regex_candidates),
                    "candidates": _summarize_candidates(regex_candidates),
                },
                "llm": llm,
                "comparison": _section_delta(regex_sections, llm_sections) if llm else None,
            }
        )
    return reports


def run_real_db(
    db_path: Path,
    limit: int,
    *,
    llm_fixtures: dict[str, Any] | None = None,
    llm_live: bool = False,
) -> list[dict]:
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
            regex_candidates = extract_candidates(messages, include_skipped=True)
            regex_sections = {candidate.section_key for candidate in regex_candidates}
            llm = _llm_report(
                messages,
                session_key=session["id"],
                group="real",
                fixtures=llm_fixtures,
                live=llm_live,
            )
            llm_sections = set(llm["sections"]) if llm else set()
            reports.append(
                {
                    "id": session["id"],
                    "title": session["title"],
                    "updated_at": session["updated_at"],
                    "message_count": session["message_count"],
                    "candidate_count": len(regex_candidates),
                    "candidates": _summarize_candidates(regex_candidates),
                    "regex": {
                        "sections": sorted(regex_sections),
                        "candidate_count": len(regex_candidates),
                        "candidates": _summarize_candidates(regex_candidates),
                    },
                    "llm": llm,
                    "comparison": _section_delta(regex_sections, llm_sections) if llm else None,
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
        for candidate in report["regex"]["candidates"]:
            marker = " skipped" if candidate["skipped"] else ""
            print(
                f"  - regex {candidate['section']}: {candidate['label']} "
                f"({candidate['confidence']:.2f}{marker})"
            )
        _print_llm_comparison(report)

    if not real:
        return

    print("\nReal DB dry-run sample")
    print("=" * 22)
    for report in real:
        print(
            f"\n{report['id']} - {report['message_count']} messages, "
            f"{report['candidate_count']} candidates"
        )
        for candidate in report["regex"]["candidates"]:
            marker = " skipped" if candidate["skipped"] else ""
            print(
                f"  - regex {candidate['section']}: {candidate['label']} "
                f"({candidate['confidence']:.2f}{marker})"
            )
        _print_llm_comparison(report)


def _print_llm_comparison(report: dict) -> None:
    llm = report.get("llm")
    if not llm:
        return
    source = llm.get("source") or "unknown"
    provider = llm.get("provider") or {}
    selected = provider.get("selected") or ""
    provider_suffix = f", provider={selected}" if selected else ""
    print(f"  llm: {llm['candidate_count']} candidates ({source}{provider_suffix})")
    comparison = report.get("comparison") or {}
    if comparison:
        print(f"  shared:     {', '.join(comparison['shared']) or '-'}")
        print(f"  regex only: {', '.join(comparison['regex_only']) or '-'}")
        print(f"  llm only:   {', '.join(comparison['llm_only']) or '-'}")
    for candidate in llm["candidates"]:
        marker = " skipped" if candidate["skipped"] else ""
        print(
            f"  - llm   {candidate['section']}: {candidate['label']} "
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
    parser.add_argument(
        "--llm-fixture",
        help=(
            "JSON fixture of raw LLM responses keyed by curated session name and/or real session id. "
            "May contain top-level keys or {'curated': {...}, 'real': {...}}."
        ),
    )
    parser.add_argument(
        "--llm-live",
        action="store_true",
        help="Call the configured provider through the AI router for LLM comparison.",
    )
    args = parser.parse_args()

    llm_fixtures = _load_llm_fixture(args.llm_fixture)
    curated = run_curated(llm_fixtures=llm_fixtures, llm_live=args.llm_live)
    real = (
        run_real_db(
            ROOT / args.db_path,
            args.limit,
            llm_fixtures=llm_fixtures,
            llm_live=args.llm_live,
        )
        if args.real_db
        else []
    )
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
