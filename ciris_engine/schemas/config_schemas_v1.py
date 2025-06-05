from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

from .guardrails_config_v1 import GuardrailsConfig

DEFAULT_SQLITE_DB_FILENAME = "ciris_engine.db"
DEFAULT_DATA_DIR = "data"
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"

class DatabaseConfig(BaseModel):
    """Minimal v1 database configuration."""
    db_filename: str = Field(default=DEFAULT_SQLITE_DB_FILENAME, alias="db_filename")
    data_directory: str = DEFAULT_DATA_DIR
    graph_memory_filename: str = Field(default="graph_memory.pkl", alias="graph_memory_filename")

from .agent_core_schemas_v1 import Task, Thought
from .action_params_v1 import *
from .foundational_schemas_v1 import HandlerActionType

class WorkflowConfig(BaseModel):
    """Workflow processing configuration for v1."""
    max_active_tasks: int = Field(default=10, description="Maximum tasks that can be active simultaneously")
    max_active_thoughts: int = Field(default=50, description="Maximum thoughts to pull into processing queue per round") 
    round_delay_seconds: float = Field(default=1.0, description="Delay between processing rounds in seconds")
    max_rounds: int = Field(default=7, description="Maximum ponder iterations before auto-defer")
    num_rounds: Optional[int] = Field(default=None, description="Maximum number of processing rounds (None = infinite)")
    DMA_RETRY_LIMIT: int = Field(default=3, description="Maximum retry attempts for DMAs")
    DMA_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout in seconds for each DMA evaluation",
    )
    GUARDRAIL_RETRY_LIMIT: int = Field(default=2, description="Maximum retry attempts for guardrails")

class OpenAIConfig(BaseModel):
    """OpenAI/LLM service configuration for v1."""
    model_name: str = Field(default="gpt-4o-mini", description="Default model name")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    timeout_seconds: float = Field(default=30.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    api_key: Optional[str] = Field(default=None, description="API key for OpenAI or compatible service")
    api_key_env_var: str = Field(default="OPENAI_API_KEY", description="Environment variable for API key")
    instructor_mode: str = Field(default="JSON", description="InGuardrailsConfiguctor library mode")

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var

        if not self.api_key:
            self.api_key = get_env_var(self.api_key_env_var)
        
        if not self.base_url:
            base_url = get_env_var("OPENAI_API_BASE") or get_env_var("OPENAI_BASE_URL")
            if base_url:
                self.base_url = base_url
        
        if not self.model_name or self.model_name == "gpt-4o-mini":
            env_model = get_env_var("OPENAI_MODEL_NAME")
            if env_model:
                self.model_name = env_model

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
    guardrails_config: Optional[GuardrailsConfig] = None

class CIRISNodeConfig(BaseModel):
    """Configuration for communicating with CIRISNode service."""

    base_url: str = Field(default="https://localhost:8001")
    timeout_seconds: float = Field(default=30.0)
    max_retries: int = Field(default=2)
    agent_secret_jwt: Optional[str] = None

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var

        env_url = get_env_var("CIRISNODE_BASE_URL")
        if env_url:
            self.base_url = env_url
        self.agent_secret_jwt = get_env_var("CIRISNODE_AGENT_SECRET_JWT")

class NetworkConfig(BaseModel):
    """Network participation configuration"""
    enabled_networks: List[str] = Field(default_factory=lambda: ["local", "cirisnode"])
    agent_identity_path: Optional[str] = None  # Path to identity file
    peer_discovery_interval: int = 300  # seconds
    reputation_threshold: int = 30  # 0-100 scale
    
class TelemetryConfig(BaseModel):
    """Telemetry configuration - secure by default"""
    enabled: bool = False
    internal_only: bool = True
    retention_hours: int = 1
    snapshot_interval_ms: int = 1000

class WisdomConfig(BaseModel):
    """Wisdom-seeking configuration"""
    wa_timeout_hours: int = 72  # Hours before considering WA unavailable
    allow_universal_guidance: bool = True  # Allow prayer protocol
    minimum_urgency_for_universal: int = 80  # 0-100 scale
    peer_consensus_threshold: int = 3  # Minimum peers for consensus

class AppConfig(BaseModel):
    """Minimal v1 application configuration."""
    version: Optional[str] = None
    log_level: Optional[str] = None
    database: DatabaseConfig = DatabaseConfig()
    llm_services: LLMServicesConfig = LLMServicesConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    workflow: WorkflowConfig = WorkflowConfig()
    cirisnode: CIRISNodeConfig = CIRISNodeConfig()
    network: NetworkConfig = NetworkConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    wisdom: WisdomConfig = WisdomConfig()
    profile_directory: str = Field(default="ciris_profiles", description="Directory containing agent profiles")
    default_profile: str = Field(default="default", description="Default agent profile name to use if not specified")
    agent_profiles: Dict[str, AgentProfile] = Field(default_factory=dict)
    discord_channel_id: Optional[str] = None

DMA_RETRY_LIMIT = 3
GUARDRAIL_RETRY_LIMIT = 2
DMA_TIMEOUT_SECONDS = 30.0
