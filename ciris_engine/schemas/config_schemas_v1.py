from pydantic import BaseModel, Field
from typing import List, Dict, Optional

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

class AgentProfile(BaseModel):
    """Minimal v1 agent profile configuration."""
    name: str
    allowed_actions: List[HandlerActionType]
    system_prompt: str

class AppConfig(BaseModel):
    """Minimal v1 application configuration."""
    version: Optional[str] = None  # Optional config versioning
    log_level: Optional[str] = None  # Optional runtime logging control (e.g., 'INFO', 'DEBUG')
    database: DatabaseConfig = DatabaseConfig()
    llm: LLMConfig = LLMConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    profiles: Dict[str, AgentProfile] = Field(default_factory=dict)