"""
Schemas for secrets filter operations.

These replace all Dict[str, Any] usage in logic/secrets/filter.py.
"""
from typing import List, Any
from pydantic import BaseModel, Field
from pydantic import Field

class PatternStats(BaseModel):
    """Statistics about active patterns."""
    total_patterns: int = Field(0, description="Total number of patterns")
    default_patterns: int = Field(0, description="Number of active default patterns")
    custom_patterns: int = Field(0, description="Number of custom patterns")
    disabled_patterns: int = Field(0, description="Number of disabled patterns")
    builtin_patterns: bool = Field(True, description="Whether builtin patterns are enabled")
    filter_version: str = Field("v1.0", description="Filter version")

class ConfigExport(BaseModel):
    """Exported configuration data."""
    filter_id: str = Field("config_based", description="Filter identifier")
    version: int = Field(1, description="Configuration version")
    builtin_patterns_enabled: bool = Field(True, description="Whether builtin patterns are enabled")
    custom_patterns: list = Field(default_factory=list, description="Custom patterns")
    disabled_patterns: List[str] = Field(default_factory=list, description="Disabled pattern names")
    sensitivity_overrides: dict = Field(default_factory=dict, description="Sensitivity overrides")
    require_confirmation_for: List[str] = Field(default_factory=list, description="Actions requiring confirmation")
    auto_decrypt_for_actions: List[str] = Field(default_factory=list, description="Actions that auto-decrypt")

class FilterConfigUpdate(BaseModel):
    """Update to filter configuration."""
    updates: dict = Field(..., description="Configuration updates to apply")
    update_type: str = Field("config", description="Type of update")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors if any")

class SecretsFilterResult(BaseModel):
    """Result of a secrets filtering operation."""
    filtered_content: str = Field(..., description="Content after filtering")
    secrets_found: List[str] = Field(default_factory=list, description="List of secrets found")
    patterns_matched: List[str] = Field(default_factory=list, description="Patterns that matched")