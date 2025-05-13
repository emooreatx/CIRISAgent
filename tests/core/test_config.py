import pytest
import json
from pathlib import Path

# Modules to test
from ciris_engine.core.config_schemas import (
    AppConfig,
    DatabaseConfig,
    OpenAIConfig,
    LLMServicesConfig,
    GuardrailsConfig,
    WorkflowConfig,
    DEFAULT_SQLITE_DB_FILENAME,
    DEFAULT_DATA_DIR,
    DEFAULT_OPENAI_MODEL_NAME
)
from ciris_engine.core import config_manager

# --- Tests for config_schemas.py ---

def test_app_config_default_instantiation():
    """Test that AppConfig and its nested models can be instantiated with defaults."""
    try:
        config = AppConfig()
        assert config.db is not None
        assert config.llm_services is not None
        assert config.llm_services.openai is not None
        assert config.guardrails is not None
        assert config.workflow is not None

        assert config.db.db_filename == DEFAULT_SQLITE_DB_FILENAME
        assert config.db.data_directory == DEFAULT_DATA_DIR
        assert config.llm_services.openai.model_name == DEFAULT_OPENAI_MODEL_NAME
        assert config.llm_services.openai.instructor_mode == "JSON" # Updated default
    except Exception as e:
        pytest.fail(f"AppConfig default instantiation failed: {e}")

def test_openai_config_fields():
    """Test specific fields and defaults in OpenAIConfig."""
    config = OpenAIConfig()
    assert config.model_name == DEFAULT_OPENAI_MODEL_NAME
    assert config.base_url is None # Default is None
    assert config.timeout_seconds == 30.0
    assert config.max_retries == 2
    assert config.api_key_env_var == "OPENAI_API_KEY"
    assert config.instructor_mode == "JSON" # Updated default

# --- Tests for config_manager.py ---

@pytest.fixture(autouse=True)
def reset_global_config_instance():
    """Fixture to reset the global _app_config in config_manager before each test."""
    config_manager._app_config = None
    yield
    config_manager._app_config = None

def test_get_config_returns_default_instance(monkeypatch):
    """Test that get_config() returns a default AppConfig instance if no file exists."""
    # Ensure no config file exists for this test
    monkeypatch.setattr(config_manager, "get_config_file_path", lambda: Path("non_existent_config.json"))
    
    config = config_manager.get_config()
    assert isinstance(config, AppConfig)
    assert config.db.db_filename == DEFAULT_SQLITE_DB_FILENAME # Check a default value

def test_load_config_from_json_file(tmp_path):
    """Test loading configuration from a JSON file."""
    config_dir = tmp_path / "config_data"
    config_dir.mkdir()
    config_file = config_dir / "test_config.json"
    
    custom_config_data = {
        "db": {"db_filename": "custom.db", "data_directory": "custom_data"},
        "llm_services": {
            "openai": {
                "model_name": "gpt-custom",
                "base_url": "http://localhost:1234",
                "instructor_mode": "JSON"
            }
        },
        "guardrails": {"entropy_threshold": 0.99},
        "workflow": {} # Assuming workflow config is empty or has defaults
    }
    with open(config_file, 'w') as f:
        json.dump(custom_config_data, f)

    # Patch get_config_file_path to point to our temp file
    original_get_path = config_manager.get_config_file_path
    config_manager.get_config_file_path = lambda: config_file
    
    try:
        loaded_config = config_manager.load_config_from_file() # Will use the patched path
        assert loaded_config.db.db_filename == "custom.db"
        assert loaded_config.db.data_directory == "custom_data"
        assert loaded_config.llm_services.openai.model_name == "gpt-custom"
        assert loaded_config.llm_services.openai.base_url == "http://localhost:1234"
        assert loaded_config.llm_services.openai.instructor_mode == "JSON"
        assert loaded_config.guardrails.entropy_threshold == 0.99
    finally:
        config_manager.get_config_file_path = original_get_path # Restore

def test_save_and_load_config(tmp_path):
    """Test saving a config and then loading it back."""
    config_dir = tmp_path / "config_data_save_load"
    config_dir.mkdir()
    config_file = config_dir / "test_save_load_config.json"

    # Create a custom config instance
    app_config = AppConfig(
        db=DatabaseConfig(db_filename="saved.db", data_directory="saved_data"),
        llm_services=LLMServicesConfig(
            openai=OpenAIConfig(model_name="gpt-saved", instructor_mode="MD_JSON")
        )
    )

    # Patch get_config_file_path for both save and load
    original_get_path = config_manager.get_config_file_path
    config_manager.get_config_file_path = lambda: config_file

    try:
        config_manager.save_config_to_json(app_config)
        assert config_file.exists()

        # Reset global config to force reload
        config_manager._app_config = None 
        loaded_config = config_manager.load_config_from_file()

        assert loaded_config.db.db_filename == "saved.db"
        assert loaded_config.llm_services.openai.model_name == "gpt-saved"
        assert loaded_config.llm_services.openai.instructor_mode == "MD_JSON"
    finally:
        config_manager.get_config_file_path = original_get_path

def test_get_config_as_json_str(monkeypatch):
    """Test getting the configuration as a JSON string."""
    # Ensure a known config state (default)
    monkeypatch.setattr(config_manager, "get_config_file_path", lambda: Path("non_existent_for_json_str.json"))
    config_manager.load_config_from_file() # Load defaults

    json_str = config_manager.get_config_as_json_str()
    assert isinstance(json_str, str)
    try:
        data = json.loads(json_str)
        assert data["db"]["db_filename"] == DEFAULT_SQLITE_DB_FILENAME
        assert data["llm_services"]["openai"]["model_name"] == DEFAULT_OPENAI_MODEL_NAME
    except json.JSONDecodeError:
        pytest.fail("get_config_as_json_str did not return valid JSON.")

def test_get_sqlite_db_full_path(monkeypatch, tmp_path):
    """Test the construction of the SQLite DB full path."""
    # Mock project root for predictability in tests
    # config_manager.get_project_root_for_config() returns Path(__file__).parent.parent
    # In tests, __file__ is tests/core/test_config.py, so parent.parent is tests/
    # We need it to resolve to a mock project root where 'cirisengine' would be.
    # Let's assume the test runner is at the actual project root (parent of cirisengine and tests)
    
    # For this test, let's make get_project_root_for_config return tmp_path
    # so that data_directory/db_filename are created inside tmp_path
    
    mock_project_root = tmp_path / "mock_ciris_engine_root"
    mock_project_root.mkdir()

    monkeypatch.setattr(config_manager, "get_project_root_for_config", lambda: mock_project_root)

    # Ensure a known config state (default)
    monkeypatch.setattr(config_manager, "get_config_file_path", lambda: Path("non_existent_for_db_path.json"))
    config = config_manager.load_config_from_file() # Load defaults (db_filename, data_directory)

    expected_path = mock_project_root / config.db.data_directory / config.db.db_filename
    
    db_full_path_str = config_manager.get_sqlite_db_full_path()
    db_full_path = Path(db_full_path_str)

    assert db_full_path.is_absolute()
    assert db_full_path == expected_path.resolve()
    # Check if the parent directory for the db was created by get_sqlite_db_full_path
    assert db_full_path.parent.exists()
    assert db_full_path.parent.is_dir()

def test_load_config_creates_default_if_not_exists_and_flag_true(tmp_path):
    config_file = tmp_path / "new_default_config.json"
    assert not config_file.exists()

    original_get_path = config_manager.get_config_file_path
    config_manager.get_config_file_path = lambda: config_file
    
    try:
        config = config_manager.load_config_from_file(create_if_not_exists=True)
        assert config_file.exists()
        with open(config_file, 'r') as f:
            data = json.load(f)
        assert data["db"]["db_filename"] == DEFAULT_SQLITE_DB_FILENAME
    finally:
        config_manager.get_config_file_path = original_get_path
