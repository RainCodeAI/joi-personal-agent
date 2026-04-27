from types import SimpleNamespace

from app.user_model.context import UserModelPromptFormatter
from app.user_model.store import UserModelCorrectionStore


class _MemoryStore:
    def get_user_profile(self, user_id):
        return SimpleNamespace(
            user_id=user_id,
            personality="Curious",
            humor_level=8,
            notes="night owl",
        )

    def get_personal_goals(self, user_id):
        return [
            SimpleNamespace(
                id=3,
                user_id=user_id,
                name="Ship Joi v2",
                description="Make Joi feel present",
                status="active",
            )
        ]

    def get_contacts(self, user_id, limit=50):
        return [
            SimpleNamespace(
                id=9,
                user_id=user_id,
                name="Bob",
            )
        ]


def test_user_model_prompt_block_includes_safe_explicit_context(tmp_path):
    formatter = UserModelPromptFormatter(
        UserModelCorrectionStore(tmp_path / "user_model_corrections.json")
    )

    block = formatter.build_prompt_block(user_id="default", memory_store=_MemoryStore())

    assert "[User Model]" in block
    assert "Use this context lightly" in block
    assert "Communication preferences:" in block
    assert "Preferred personality mode: Curious." in block
    assert "Ship Joi v2: Make Joi feel present" in block
    assert "Bob appears in the explicit contact list." in block


def test_user_model_prompt_block_applies_hide_delete_and_add(tmp_path):
    store = UserModelCorrectionStore(tmp_path / "user_model_corrections.json")
    store.record(
        user_id="default",
        section_key="active_projects",
        action="hide",
        item_id="active_projects:3",
    )
    store.record(
        user_id="default",
        section_key="stated_goals",
        action="delete",
        item_id="stated_goals:3",
    )
    store.record(
        user_id="default",
        section_key="communication_preferences",
        action="add",
        label="Tone",
        value="Use a restrained, direct voice.",
    )
    formatter = UserModelPromptFormatter(store)

    block = formatter.build_prompt_block(user_id="default", memory_store=_MemoryStore())

    assert "Tone: Use a restrained, direct voice." in block
    assert "Active projects:" not in block
    assert "Stated goals:" not in block
    assert "Ship Joi v2" not in block


def test_user_model_prompt_formatter_sees_corrections_from_another_store_instance(tmp_path):
    path = tmp_path / "user_model_corrections.json"
    writer = UserModelCorrectionStore(path)
    reader = UserModelCorrectionStore(path)
    formatter = UserModelPromptFormatter(reader)

    writer.record(
        user_id="default",
        section_key="communication_preferences",
        action="add",
        label="Pacing",
        value="Keep replies concise.",
    )

    block = formatter.build_prompt_block(user_id="default", memory_store=_MemoryStore())

    assert "Pacing: Keep replies concise." in block
