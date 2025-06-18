import pytest
import tempfile
import yaml
import asyncio
from pathlib import Path
from ciris_engine.utils.profile_loader import load_template


@pytest.mark.asyncio
async def test_load_template(tmp_path):
    profile_path = tmp_path / "test.yaml"
    profile_data = {
        "name": "test",
        "description": "Test profile",
        "role_description": "A test agent profile"
    }
    with open(profile_path, "w") as f:
        yaml.safe_dump(profile_data, f)
    profile = await load_template(profile_path)
    assert profile.name == "test"
    assert profile.description == "Test profile"
    assert profile.role_description == "A test agent profile"


@pytest.mark.asyncio
async def test_profile_with_overrides(tmp_path):
    profile_path = tmp_path / "teacher.yaml"
    profile_data = {
        "name": "Teacher",
        "description": "Teacher profile with overrides",
        "role_description": "A teacher agent that guides through questions",
        "action_selection_pdma_overrides": {
            "teacher_mode_action_params_observe_guidance": "OBSERVE guidance"
        },
    }
    with open(profile_path, "w") as f:
        yaml.safe_dump(profile_data, f)

    profile = await load_template(profile_path)
    assert (
        profile.action_selection_pdma_overrides[
            "teacher_mode_action_params_observe_guidance"
        ]
        == "OBSERVE guidance"
    )
