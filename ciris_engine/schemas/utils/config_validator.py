"""
Schemas for config validator operations.

These replace all Dict[str, Any] usage in logic/utils/config_validator.py.
"""
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class ConfigData(BaseModel):
    """Configuration data for validation."""
    llm_services: dict = Field(default_factory=dict, description="LLM services config")
    database: dict = Field(default_factory=dict, description="Database config")
    secrets: dict = Field(default_factory=dict, description="Secrets config")
    additional_config: dict = Field(default_factory=dict, description="Other configuration")

class LLMConfig(BaseModel):
    """LLM configuration."""
    openai: dict = Field(default_factory=dict, description="OpenAI config")
    additional_providers: dict = Field(default_factory=dict, description="Other LLM providers")

# OpenAIConfig moved to schemas/config/core.py to avoid duplication

class DatabaseValidationConfig(BaseModel):
    """Database configuration for validation."""
    db_filename: Optional[str] = Field(None, description="Database filename")
    additional_settings: dict = Field(default_factory=dict, description="Other database settings")

class MaskedConfigResult(BaseModel):
    """Result of masking sensitive configuration values."""
    masked_config: dict = Field(..., description="Configuration with masked sensitive values")
    masked_count: int = Field(0, description="Number of values masked")
    masked_paths: List[str] = Field(default_factory=list, description="Paths that were masked")

class NestedValueUpdate(BaseModel):
    """Represents a nested value update operation."""
    target_object: dict = Field(..., description="Object to update")
    path: str = Field(..., description="Dot-separated path")
    value: Any = Field(..., description="Value to set")
    original_value: Any = Field(None, description="Original value before update")
