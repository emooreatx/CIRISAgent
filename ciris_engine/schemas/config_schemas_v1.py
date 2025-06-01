from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

# Default values used across tests and services
DEFAULT_SQLITE_DB_FILENAME = "ciris_engine.db"
DEFAULT_DATA_DIR = "data"
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"

class DatabaseConfig(BaseModel):
    """Minimal v1 database configuration."""
    db_filename: str = Field(default=DEFAULT_SQLITE_DB_FILENAME, alias="db_filename")
    data_directory: str = DEFAULT_DATA_DIR
    graph_memory_filename: str = Field(default="graph_memory.pkl", alias="graph_memory_filename")

from .guardrails_config_v1 import GuardrailsConfig
from .agent_core_schemas_v1 import Task, Thought
from .action_params_v1 import *
from .foundational_schemas_v1 import HandlerActionType

class WorkflowConfig(BaseModel):
    """Workflow processing configuration for v1."""
    max_active_tasks: int = Field(default=10, description="Maximum tasks that can be active simultaneously")
    max_active_thoughts: int = Field(default=50, description="Maximum thoughts to pull into processing queue per round") 
    round_delay_seconds: float = Field(default=1.0, description="Delay between processing rounds in seconds")
    max_rounds: int = Field(default=5, description="Maximum ponder iterations before auto-defer")
    num_rounds: Optional[int] = Field(default=None, description="Maximum number of processing rounds (None = infinite)")
    DMA_RETRY_LIMIT: int = Field(default=3, description="Maximum retry attempts for DMAs")
    GUARDRAIL_RETRY_LIMIT: int = Field(default=2, description="Maximum retry attempts for guardrails")

class OpenAIConfig(BaseModel):
    """OpenAI/LLM service configuration for v1."""
    model_name: str = Field(default="gpt-4o-mini", description="Default model name")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    timeout_seconds: float = Field(default=30.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    api_key_env_var: str = Field(default="OPENAI_API_KEY", description="Environment variable for API key")
    instructor_mode: str = Field(default="JSON", description="Instructor library mode")

class LLMServicesConfig(BaseModel):
    """LLM services configuration container."""
    openai: OpenAIConfig = OpenAIConfig()

class AgentProfile(BaseModel):
    """Minimal v1 agent profile configuration."""
    name: str
    dsdma_identifier: Optional[str] = None
    dsdma_kwargs: Optional[Dict[str, Any]] = None
    permitted_actions: List[HandlerActionType] = Field(default_factory=list)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)

class CIRISNodeConfig(BaseModel):
    """Configuration for communicating with CIRISNode service."""

    base_url: str = Field(default="https://localhost:8001")
    timeout_seconds: float = Field(default=30.0)
    max_retries: int = Field(default=2)
    agent_secret_jwt: Optional[str] = None

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        import os

        env_url = os.getenv("CIRISNODE_BASE_URL")
        if env_url:
            self.base_url = env_url
        self.agent_secret_jwt = os.getenv("CIRISNODE_AGENT_SECRET_JWT")

class AppConfig(BaseModel):
    """Minimal v1 application configuration."""
    version: Optional[str] = None
    log_level: Optional[str] = None
    database: DatabaseConfig = DatabaseConfig()
    llm_services: LLMServicesConfig = LLMServicesConfig()  # Updated structure
    guardrails: GuardrailsConfig = GuardrailsConfig()
    workflow: WorkflowConfig = WorkflowConfig()
    cirisnode: CIRISNodeConfig = CIRISNodeConfig()  # Add cirisnode configuration
    profile_directory: str = Field(default="ciris_profiles", description="Directory containing agent profiles")
    default_profile: str = Field(default="default", description="Default agent profile name to use if not specified")
    agent_profiles: Dict[str, AgentProfile] = Field(default_factory=dict)
    discord_channel_id: Optional[str] = None  # Add this field for Discord channel id

# Expose commonly used constants at module level for convenience
DMA_RETRY_LIMIT = 3
GUARDRAIL_RETRY_LIMIT = 2
