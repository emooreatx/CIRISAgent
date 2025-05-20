import os
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Import HandlerActionType for use in profile schema
from .foundational_schemas import HandlerActionType

# These default values are based on the old config.py.
# They will be used if a configuration is not explicitly set elsewhere (e.g., via a config file).

# It's generally better to define defaults directly in the Field or as factory functions
# if they are simple. For complex defaults or shared constants, this approach is okay.
# However, for path construction, using os.path.join at the module level like this
# means it's resolved when the module is first imported.
# A config manager would typically handle resolving paths relative to a config file or project root.
# For simplicity here, we'll keep it, but note this for a more robust implementation.
DEFAULT_SQLITE_DB_FILENAME = "ciris_engine.db" # Just the filename
DEFAULT_DATA_DIR = "data"

DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 60.0
DEFAULT_OPENAI_MAX_RETRIES = 2
DEFAULT_ENTROPY_THRESHOLD = 0.40
DEFAULT_COHERENCE_THRESHOLD = 0.80
# Default retry limit for DMAs
DMA_RETRY_LIMIT = 3
# Default priorities are already in agent_core_schemas.py for Task and Thought.
# If they need to be *dynamically configurable* by wise authorities,
# they can be included in WorkflowConfig.
# For now, let's assume the Pydantic model defaults are sufficient unless overridden by a loaded config.
# DEFAULT_TASK_PRIORITY = 0
# DEFAULT_THOUGHT_PRIORITY = 0


class DatabaseConfig(BaseModel):
    """Configuration for the database."""
    # Path will be constructed by a config manager, e.g., os.path.join(project_root, data_dir, db_filename)
    db_filename: str = Field(default=DEFAULT_SQLITE_DB_FILENAME, description="Filename for the SQLite database.")
    data_directory: str = Field(default=DEFAULT_DATA_DIR, description="Directory to store data files, relative to project root.")
    # sqlite_db_path: str will be a constructed property or handled by the manager

class OpenAIConfig(BaseModel):
    """Configuration for the OpenAI client."""
    model_name: str = Field(default=DEFAULT_OPENAI_MODEL_NAME, description="Default OpenAI model name.")
    base_url: Optional[str] = Field(default=None, description="Optional base URL for the OpenAI API (e.g., for local LLMs).")
    timeout_seconds: float = Field(default=DEFAULT_OPENAI_TIMEOUT_SECONDS, description="Default timeout for OpenAI API calls.")
    max_retries: int = Field(default=DEFAULT_OPENAI_MAX_RETRIES, description="Default max retries for OpenAI API calls.")
    api_key_env_var: str = Field(default="OPENAI_API_KEY", description="Environment variable name for the OpenAI API key. The actual key is loaded from the environment.")
    instructor_mode: str = Field(default="JSON", description="Mode for instructor library (e.g., TOOLS, JSON, MD_JSON, FUNCTIONS).") # Changed default to JSON

class LLMServicesConfig(BaseModel):
    """Configuration for all LLM services."""
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    # Example: anthropic: Optional[AnthropicConfig] = None

class CIRISNodeConfig(BaseModel):
    """Configuration for CIRISNode integration."""
    base_url_env_var: str = Field(default="CIRISNODE_BASE_URL", description="Environment variable for CIRISNode base URL.")
    base_url: str = Field(default="http://localhost:8001", description="Base URL for the CIRISNode service.")

    def load_env_vars(self):
        self.base_url = os.getenv(self.base_url_env_var, self.base_url)

class GuardrailsConfig(BaseModel):
    """Configuration for guardrails."""
    entropy_threshold: float = Field(default=DEFAULT_ENTROPY_THRESHOLD, description="Threshold for entropy guardrail.")
    coherence_threshold: float = Field(default=DEFAULT_COHERENCE_THRESHOLD, description="Threshold for coherence guardrail.")

class WorkflowConfig(BaseModel):
    """Configuration for core workflow settings."""
    # If default priorities need to be dynamically configured:
    # default_task_priority: int = Field(default=0, description="Default priority for new tasks.")
    # default_thought_priority: int = Field(default=0, description="Default priority for new thoughts.")
    max_active_tasks: int = Field(default=10, description="Maximum number of tasks that can be in an 'active' state simultaneously.")
    max_active_thoughts: int = Field(default=50, description="Maximum number of thoughts that can be in an 'active' or 'processing' state across all tasks.") # Or per task, needs clarification if used.
    round_delay_seconds: float = Field(default=1.0, ge=0.0, description="Delay in seconds between processing rounds.") # Added round delay
    max_ponder_rounds: int = Field(default=5, ge=0, description="Maximum number of times a thought can be re-queued via PONDER action before deferral.") # Added max ponder rounds


# --- Serializable Agent Profile Schema ---

class SerializableAgentProfile(BaseModel):
    """
    Serializable configuration for an agent profile.
    Replaces the non-serializable dataclass version.
    """
    name: str = Field(..., description="Unique name for the profile (e.g., 'Teacher', 'Student').")
    dsdma_identifier: Optional[str] = Field(None, description="Identifier string for the DSDMA class to use (e.g., 'BasicTeacherDSDMA'). None means no DSDMA.")
    dsdma_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Keyword arguments to pass when instantiating the DSDMA class.")
    permitted_actions: List[HandlerActionType] = Field(default_factory=list, description="List of actions this profile is allowed to select.")
    csdma_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional overrides for CSDMA (e.g., prompt adjustments). Currently unused.")
    action_selection_pdma_overrides: Optional[Dict[str, str]] = Field(default_factory=dict, description="Optional overrides for Action Selection PDMA prompts (e.g., 'system_header').")

class AppConfig(BaseModel):
    """
    Root configuration model for the CIRISEngine application.
    This model can be instantiated with default values, loaded from a JSON file,
    and serialized to JSON for exposure.
    """
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm_services: LLMServicesConfig = Field(default_factory=LLMServicesConfig)
    cirisnode: CIRISNodeConfig = Field(default_factory=CIRISNodeConfig)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    profile_directory: str = Field(default="ciris_profiles", description="Directory containing agent profile YAML files, relative to project root.")
    # Agent profiles can also be defined directly in the config if not loaded from separate files
    agent_profiles: Dict[str, SerializableAgentProfile] = Field(default_factory=dict, description="Dictionary of available agent profiles, keyed by profile name (can be populated from profile_directory or defined here).")
    enable_remote_graphql: bool = Field(default=False, description="When False, disable remote GraphQL lookups and rely solely on local memory.")

    class Config:
        # Example for Pydantic v2 if using model_config
        # model_config = {
        #     "json_schema_extra": {
        #         "examples": [
        #             {
        #                 "db": {"db_filename": "my_agent.db", "data_directory": "app_data"},
        #                 "llm_services": {"openai": {"model_name": "gpt-3.5-turbo"}},
        #                 "guardrails": {"entropy_threshold": 0.45},
        #                 "workflow": {}
        #             }
        #         ]
        #     }
        # }
        pass # Add Pydantic config options if needed, e.g., for aliasing or schema generation.
