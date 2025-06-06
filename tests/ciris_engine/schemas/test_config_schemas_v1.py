from ciris_engine.schemas.config_schemas_v1 import DatabaseConfig, WorkflowConfig, OpenAIConfig

def test_database_config_defaults():
    config = DatabaseConfig()
    assert config.db_filename
    assert config.data_directory == "data"
    assert config.graph_memory_filename == "graph_memory.pkl"

def test_openai_config_defaults():
    config = OpenAIConfig()
    assert config.model_name
    assert config.timeout_seconds == 30.0
    assert config.max_retries == 3
    assert config.api_key_env_var == "OPENAI_API_KEY"
    assert config.instructor_mode == "JSON"

def test_workflow_config_defaults():
    config = WorkflowConfig()
    assert config.max_active_tasks == 10
    assert config.max_active_thoughts == 50
    assert config.round_delay_seconds == 1.0
    assert config.max_rounds == 7
    assert config.DMA_RETRY_LIMIT == 3
    assert config.GUARDRAIL_RETRY_LIMIT == 2
    assert config.DMA_TIMEOUT_SECONDS == 30.0
