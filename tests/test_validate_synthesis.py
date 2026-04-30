from pathlib import Path

from scripts import validate_synthesis


def test_run_curated_compares_regex_and_llm_fixture():
    fixtures = {
        "curated": {
            "project_goal_worry": {
                "candidates": [
                    {
                        "section_key": "active_projects",
                        "label": "User model diagnostics page",
                        "value": "User is building the user model diagnostics page tonight.",
                        "confidence": 0.87,
                        "source_excerpt": "I'm building the user model diagnostics page tonight.",
                        "source_message_index": 0,
                        "source_message_role": "user",
                    },
                    {
                        "section_key": "stated_goals",
                        "label": "Trustworthy memory",
                        "value": "User wants Joi's memory to feel trustworthy before inference is enabled.",
                        "confidence": 0.9,
                        "source_excerpt": "My goal is to make Joi's memory feel trustworthy before we enable inference.",
                        "source_message_index": 1,
                        "source_message_role": "user",
                    },
                ]
            }
        }
    }

    reports = validate_synthesis.run_curated(llm_fixtures=fixtures)
    report = next(item for item in reports if item["name"] == "project_goal_worry")

    assert report["regex"]["candidate_count"] == 4
    assert report["llm"]["source"] == "fixture"
    assert report["llm"]["candidate_count"] == 2
    assert report["comparison"]["shared"] == ["active_projects", "stated_goals"]
    assert report["comparison"]["regex_only"] == ["open_loops", "recurring_worries"]
    assert report["comparison"]["llm_only"] == []


def test_load_llm_fixture_accepts_grouped_file():
    path = Path("tests/fixtures/synthesis_llm_fixture.json")

    fixtures = validate_synthesis._load_llm_fixture(str(path))
    reports = validate_synthesis.run_curated(llm_fixtures=fixtures)
    report = next(item for item in reports if item["name"] == "small_talk_negative_control")

    assert report["llm"]["candidate_count"] == 0
    assert report["comparison"] == {"shared": [], "regex_only": [], "llm_only": []}
