from pathlib import Path

from ciris_engine.config.env_utils import load_env_file, get_env_var, get_discord_channel_id
from ciris_engine.schemas.config_schemas_v1 import AppConfig


def test_env_file_precedence(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("MYVAR=file\nDISCORD_CHANNEL_ID=file-id\n")
    monkeypatch.setenv("MYVAR", "env")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "env-id")

    load_env_file(env_path, force=True)

    assert get_env_var("MYVAR") == "file"
    assert get_discord_channel_id(None) == "file-id"
    # Reset
    load_env_file(Path(".env"), force=True)


def test_app_config_precedence(monkeypatch):
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "env-id")
    cfg = AppConfig(discord_channel_id="cfg-id")
    assert get_discord_channel_id(cfg) == "cfg-id"
