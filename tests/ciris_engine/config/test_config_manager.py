import os
import tempfile
import json
import pytest
from pathlib import Path
from ciris_engine.config import config_manager
from ciris_engine.schemas.config_schemas_v1 import AppConfig

def test_load_config_from_file_defaults(tmp_path):
    # Should return default AppConfig if file does not exist
    config_path = tmp_path / "test_config.json"
    config = config_manager.load_config_from_file(config_file_path=config_path)
    assert isinstance(config, AppConfig)
    assert config.database.db_filename
    assert config.llm_services.openai.model_name

def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "test_config.json"
    config = AppConfig()
    config.database.db_filename = "custom.db"
    config_manager.save_config_to_json(config, config_file_path=config_path)
    loaded = config_manager.load_config_from_file(config_file_path=config_path)
    assert loaded.database.db_filename == "custom.db"

def test_env_override(monkeypatch, tmp_path):
    """Environment variables should not override explicit config values."""
    config_path = tmp_path / "test_config.json"
    with open(config_path, "w") as f:
        json.dump({"discord_channel_id": "file-val"}, f)

    monkeypatch.setenv("DISCORD_CHANNEL_ID", "env-override")
    config = config_manager.load_config_from_file(config_file_path=config_path)
    assert config.discord_channel_id == "file-val"


def test_env_fallback(monkeypatch, tmp_path):
    """Environment variable used when value missing in config."""
    config_path = tmp_path / "missing.json"
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "env-val")
    config = config_manager.load_config_from_file(config_file_path=config_path)
    assert config.discord_channel_id == "env-val"

def test_get_config_file_path_and_root():
    path = config_manager.get_config_file_path()
    assert path.name == config_manager.DEFAULT_CONFIG_FILENAME
    root = config_manager.get_project_root_for_config()
    assert root.exists() or root.is_dir()  # Should be a directory

def test_get_config_as_json_str():
    json_str = config_manager.get_config_as_json_str()
    assert json.loads(json_str)

def test_sqlite_db_full_path_and_graph_memory_full_path():
    db_path = config_manager.get_sqlite_db_full_path()
    graph_path = config_manager.get_graph_memory_full_path()
    assert db_path.endswith(".db")
    assert graph_path.endswith(".pkl")
