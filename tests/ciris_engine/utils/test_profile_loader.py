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
