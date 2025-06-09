import pytest
import tempfile
import yaml
import asyncio
from pathlib import Path
from ciris_engine.utils.profile_loader import load_profile


@pytest.mark.asyncio
async def test_load_profile(tmp_path):
    profile_path = tmp_path / "test.yaml"
    profile_data = {"name": "test", "dsdma_identifier": "BaseDSDMA"}
    with open(profile_path, "w") as f:
        yaml.safe_dump(profile_data, f)
    profile = await load_profile(profile_path)
    assert profile.name == "test"
    assert profile.dsdma_identifier == "BaseDSDMA"


@pytest.mark.asyncio
async def test_profile_with_overrides(tmp_path):
    profile_path = tmp_path / "teacher.yaml"
    profile_data = {
        "name": "Teacher",
        "dsdma_identifier": "BaseDSDMA",
        "action_selection_pdma_overrides": {
            "teacher_mode_action_params_observe_guidance": "OBSERVE guidance"
        },
    }
    with open(profile_path, "w") as f:
        yaml.safe_dump(profile_data, f)

    profile = await load_profile(profile_path)
    assert (
        profile.action_selection_pdma_overrides[
            "teacher_mode_action_params_observe_guidance"
        ]
        == "OBSERVE guidance"
    )
