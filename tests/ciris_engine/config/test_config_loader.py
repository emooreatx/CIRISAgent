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
        # Create a proper AgentProfile definition for the "agent" profile
        yaml.safe_dump({
            "name": "agent"
            # The discord_config will be created empty and populated by env vars
        }, f)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "123")

    config = await ConfigLoader.load_config(base, "agent")
    assert config.database.db_filename == "base.db"  # Should come from base config since profile doesn't override it
    # The home channel ID should now be sourced from the active agent profile's discord_config
    active_profile = config.agent_profiles.get("agent")
    assert active_profile is not None
    assert active_profile.discord_config is not None
    # DISCORD_CHANNEL_ID is loaded as a monitored channel and potentially as home_channel_id by DiscordAdapterConfig.load_env_vars
    # and then retrieved by get_home_channel_id()
    assert active_profile.discord_config.get_home_channel_id() == "123"


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
