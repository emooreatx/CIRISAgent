import yaml
import pytest


from ciris_engine.config.config_loader import ConfigLoader
from ciris_engine.config.dynamic_config import ConfigManager


@pytest.mark.asyncio
async def test_load_config_overlays(tmp_path, monkeypatch):
    base = tmp_path / "base.yaml"
    profile_dir = tmp_path / "ciris_profiles"
    profile_dir.mkdir()
    profile = profile_dir / "agent.yaml"

    with open(base, "w") as f:
        yaml.safe_dump({"database": {"db_filename": "base.db"}}, f)

    with open(profile, "w") as f:
        yaml.safe_dump({"database": {"db_filename": "profile.db"}}, f)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")

    config = await ConfigLoader.load_config(base, "agent")
    assert config.database.db_filename == "profile.db"
    assert config.discord_channel_id == "123"


@pytest.mark.asyncio
async def test_config_manager_update_and_reload(tmp_path, monkeypatch):
    base = tmp_path / "base.yaml"
    profiles = tmp_path / "ciris_profiles"
    profiles.mkdir()
    prof1 = profiles / "p1.yaml"
    prof2 = profiles / "p2.yaml"

    with open(base, "w") as f:
        yaml.safe_dump({"database": {"db_filename": "base.db"}}, f)

    with open(prof1, "w") as f:
        yaml.safe_dump({"database": {"db_filename": "p1.db"}}, f)

    with open(prof2, "w") as f:
        yaml.safe_dump({"database": {"db_filename": "p2.db"}}, f)

    monkeypatch.chdir(tmp_path)
    cfg = await ConfigLoader.load_config(base, "p1")
    mgr = ConfigManager(cfg)

    await mgr.update_config("database.db_filename", "updated.db")
    assert mgr.config.database.db_filename == "updated.db"

    await mgr.reload_profile("p2", base)
    assert mgr.config.database.db_filename == "p2.db"
