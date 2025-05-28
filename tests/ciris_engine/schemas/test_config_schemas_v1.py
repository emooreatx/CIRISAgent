from ciris_engine.schemas.config_schemas_v1 import DatabaseConfig, LLMConfig, WorkflowConfig

def test_database_config_defaults():
    config = DatabaseConfig()
    assert config.db_filename
    assert config.data_directory == "data"
    assert config.graph_memory_filename == "graph_memory.pkl"

def test_llm_config_defaults():
    config = LLMConfig()
    assert config.model
    assert config.temperature == 0.7
    assert config.max_retries == 2
    assert config.api_base.startswith("https://")
    assert config.max_tokens > 0
    assert config.timeout > 0
    assert config.instructor_mode == "JSON"

def test_workflow_config_defaults():
    config = WorkflowConfig()
    assert config.max_active_tasks == 10
    assert config.max_active_thoughts == 50
    assert config.round_delay_seconds == 1.0
    assert config.max_ponder_rounds == 5
    assert config.DMA_RETRY_LIMIT == 3
    assert config.GUARDRAIL_RETRY_LIMIT == 2
