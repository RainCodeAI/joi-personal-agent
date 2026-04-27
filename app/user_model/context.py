from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.user_model.store import UserModelCorrectionStore


@dataclass
class PromptUserModelItem:
    section_key: str
    item_id: str
    label: str
    value: str
    explicit: bool = True
    confirmed: bool = False
    hidden: bool = False


SECTION_TITLES = {
    "communication_preferences": "Communication preferences",
    "stated_goals": "Stated goals",
    "active_projects": "Active projects",
    "important_people": "Important people",
    "character_notes": "Character notes",
}

SECTION_ORDER = [
    "communication_preferences",
    "stated_goals",
    "active_projects",
    "important_people",
    "character_notes",
]


class UserModelPromptFormatter:
    """Formats safe user-model context for the conversation prompt."""

    def __init__(self, correction_store: UserModelCorrectionStore | None = None) -> None:
        self.correction_store = correction_store or UserModelCorrectionStore()

    def build_prompt_block(self, *, user_id: str, memory_store: Any) -> str:
        items = self._project_explicit_items(user_id=user_id, memory_store=memory_store)
        self._apply_corrections(user_id=user_id, items=items)
        visible = [
            item
            for item in items.values()
            if not item.hidden and (item.explicit or item.confirmed)
        ]
        if not visible:
            return ""

        lines = [
            "[User Model]",
            "Use this context lightly and only when relevant. Do not recite it back unprompted.",
        ]
        for section_key in SECTION_ORDER:
            section_items = [item for item in visible if item.section_key == section_key]
            if not section_items:
                continue
            lines.append(f"{SECTION_TITLES[section_key]}:")
            for item in section_items[:5]:
                value = item.value.strip()
                if not value:
                    continue
                if item.label and item.label != value:
                    lines.append(f"- {item.label}: {value}")
                else:
                    lines.append(f"- {value}")
        return "\n".join(lines).strip()

    def _project_explicit_items(self, *, user_id: str, memory_store: Any) -> dict[str, PromptUserModelItem]:
        items: dict[str, PromptUserModelItem] = {}

        try:
            profile = memory_store.get_user_profile(user_id)
        except Exception:
            profile = None
        if profile is not None:
            personality = str(getattr(profile, "personality", "") or "").strip()
            if personality:
                self._put(
                    items,
                    PromptUserModelItem(
                        section_key="communication_preferences",
                        item_id=f"communication_preferences:{user_id}:personality",
                        label="Persona preference",
                        value=f"Preferred personality mode: {personality}.",
                        confirmed=True,
                    ),
                )
            humor = getattr(profile, "humor_level", None)
            if humor is not None:
                self._put(
                    items,
                    PromptUserModelItem(
                        section_key="communication_preferences",
                        item_id=f"communication_preferences:{user_id}:humor",
                        label="Humor level",
                        value=f"Humor level is set to {humor}/10.",
                        confirmed=True,
                    ),
                )
            notes = str(getattr(profile, "notes", "") or "").strip()
            if notes:
                self._put(
                    items,
                    PromptUserModelItem(
                        section_key="character_notes",
                        item_id=f"character_notes:{user_id}:profile-notes",
                        label="Explicit profile notes",
                        value=notes,
                        confirmed=True,
                    ),
                )

        try:
            goals = memory_store.get_personal_goals(user_id)
        except Exception:
            goals = []
        for goal in goals:
            if getattr(goal, "status", "active") != "active":
                continue
            label = str(getattr(goal, "name", "") or "").strip()
            if not label:
                continue
            description = str(getattr(goal, "description", "") or "").strip()
            goal_id = str(getattr(goal, "id", label))
            self._put(
                items,
                PromptUserModelItem(
                    section_key="stated_goals",
                    item_id=f"stated_goals:{goal_id}",
                    label=label,
                    value=description or label,
                    confirmed=True,
                ),
            )
            self._put(
                items,
                PromptUserModelItem(
                    section_key="active_projects",
                    item_id=f"active_projects:{goal_id}",
                    label=label,
                    value=description or f"{label} is currently active.",
                    confirmed=True,
                ),
            )

        try:
            contacts = memory_store.get_contacts(user_id, limit=50)
        except Exception:
            contacts = []
        for contact in contacts:
            name = str(getattr(contact, "name", "") or "").strip()
            if not name:
                continue
            contact_id = str(getattr(contact, "id", name))
            self._put(
                items,
                PromptUserModelItem(
                    section_key="important_people",
                    item_id=f"important_people:{contact_id}",
                    label=name,
                    value=f"{name} appears in the explicit contact list.",
                    confirmed=True,
                ),
            )

        return items

    def _apply_corrections(self, *, user_id: str, items: dict[str, PromptUserModelItem]) -> None:
        for correction in self.correction_store.list_for_user(user_id):
            section_key = str(correction.get("section_key") or "")
            action = str(correction.get("action") or "")
            item_id = str(correction.get("item_id") or "")
            if action == "add":
                if not item_id:
                    continue
                label = str(correction.get("label") or correction.get("value") or "User supplied item").strip()
                value = str(correction.get("value") or label).strip()
                if not value:
                    continue
                items[item_id] = PromptUserModelItem(
                    section_key=section_key,
                    item_id=item_id,
                    label=label,
                    value=value,
                    explicit=False,
                    confirmed=True,
                )
                continue

            item = items.get(item_id)
            if item is None:
                continue
            if action == "confirm":
                item.confirmed = True
            elif action == "edit":
                if correction.get("label"):
                    item.label = str(correction["label"])
                if correction.get("value"):
                    item.value = str(correction["value"])
                item.confirmed = True
            elif action == "hide":
                item.hidden = True
            elif action == "delete":
                items.pop(item_id, None)

    @staticmethod
    def _put(items: dict[str, PromptUserModelItem], item: PromptUserModelItem) -> None:
        items[item.item_id] = item
