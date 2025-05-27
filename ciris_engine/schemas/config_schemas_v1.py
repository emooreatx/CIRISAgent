from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class DatabaseConfig(BaseModel):
    """Minimal v1 database configuration."""
    path: str = "ciris_engine.db"

class LLMConfig(BaseModel):
    """Minimal v1 LLM configuration."""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_retries: int = 2
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_tokens: int = 4096
    timeout: int = 60
    instructor_mode: str = "JSON"  # Default instructor mode is JSON
    # Add more fields as needed for v1 compatibility

from .guardrails_config_v1 import GuardrailsConfig
from .agent_core_schemas_v1 import Task, Thought
from .action_params_v1 import *
from .foundational_schemas_v1 import HandlerActionType

class WorkflowConfig(BaseModel):
    """Workflow processing configuration for v1."""
    max_active_tasks: int = Field(default=10, description="Maximum tasks that can be active simultaneously")
    max_active_thoughts: int = Field(default=50, description="Maximum thoughts to pull into processing queue per round") 
    round_delay_seconds: float = Field(default=1.0, description="Delay between processing rounds in seconds")
    max_ponder_rounds: int = Field(default=5, description="Maximum ponder iterations before auto-defer")
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
    permitted_actions: List[str] = Field(default_factory=list)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict) 
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)

class AppConfig(BaseModel):
    """Minimal v1 application configuration."""
    version: Optional[str] = None
    log_level: Optional[str] = None
    database: DatabaseConfig = DatabaseConfig()
    llm_services: LLMServicesConfig = LLMServicesConfig()  # Updated structure
    guardrails: GuardrailsConfig = GuardrailsConfig()
    workflow: WorkflowConfig = WorkflowConfig()
    profile_directory: str = Field(default="ciris_profiles", description="Directory containing agent profiles")
    agent_profiles: Dict[str, AgentProfile] = Field(default_factory=dict)