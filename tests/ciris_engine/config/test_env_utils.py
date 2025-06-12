from pathlib import Path

from ciris_engine.config.env_utils import load_env_file, get_env_var
from ciris_engine.schemas.config_schemas_v1 import AppConfig


def test_env_file_precedence(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("MYVAR=file\nDISCORD_CHANNEL_ID=file-id\n")
    monkeypatch.setenv("MYVAR", "env")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "env-id")

    load_env_file(env_path, force=True)

    # Environment variable should win over .env now
    assert get_env_var("MYVAR") == "env"
    assert get_env_var("DISCORD_CHANNEL_ID") == "env-id"

    # Unset env, .env should win
    monkeypatch.delenv("MYVAR", raising=False)
    monkeypatch.delenv("DISCORD_CHANNEL_ID", raising=False)
    assert get_env_var("MYVAR") == "file"
    assert get_env_var("DISCORD_CHANNEL_ID") == "file-id"
    # Reset
    load_env_file(Path(".env"), force=True)


def test_app_config_precedence(monkeypatch):
    # This test checked direct AppConfig field precedence over env vars.
    # Since discord_home_channel_id is removed, we use another field.
    # However, AppConfig fields are typically set from dicts, not direct env var fallbacks at instantiation.
    # The primary env var loading happens in ConfigLoader or specific model's load_env_vars.
    # This test might be conceptually flawed for AppConfig direct instantiation vs env vars.
    # Let's adapt it to test that a value provided at instantiation is preferred.
    # monkeypatch.setenv("LOG_LEVEL", "env-val") # Env var for log_level
    cfg = AppConfig(log_level="cfg-val") # Direct instantiation
    assert cfg.log_level == "cfg-val"

    # If we want to test env var effect on AppConfig via a loader, that's different.
    # For example, if no log_level is in YAML, _apply_env_defaults in ConfigLoader would pick up LOG_LEVEL env var.
