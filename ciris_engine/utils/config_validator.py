"""Configuration validation component for runtime config management."""
import logging
from typing import Any, Dict, List, Optional

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.runtime_control_schemas import (
    ConfigValidationLevel,
    ConfigValidationResponse,
)

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Handles configuration validation logic."""

    def __init__(self) -> None:
        """Initialize the configuration validator."""
        self._restricted_paths = {
            "llm_services.openai.api_key": "API key changes should use environment variables",
            "database.db_filename": "Database path changes require restart",
            "secrets.storage_path": "Secrets path changes require restart"
        }
        self._sensitive_keys = {
            "api_key", "password", "secret", "token", "key", "auth",
            "credential", "private", "sensitive"
        }

    async def validate_config(
        self,
        config_data: Dict[str, Any],
        config_path: Optional[str] = None,
        current_config: Optional[AppConfig] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        try:
            errors = []
            warnings = []
            suggestions = []
            
            try:
                if config_path and current_config:
                    current_config_dict = current_config.model_dump()
                    test_config = current_config_dict.copy()
                    self._set_nested_value(test_config, config_path, config_data)
                    AppConfig(**test_config)
                else:
                    AppConfig(**config_data)
            except Exception as e:
                errors.append(str(e))
            
            if "llm_services" in config_data:
                llm_warnings = self._validate_llm_config(config_data["llm_services"])
                warnings.extend(llm_warnings)
            
            if "database" in config_data:
                db_suggestions = self._validate_database_config(config_data["database"])
                suggestions.extend(db_suggestions)
            
            return ConfigValidationResponse(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Failed to validate config: {e}")
            return ConfigValidationResponse(
                valid=False,
                errors=[f"Validation error: {str(e)}"]
            )

    async def validate_config_update(
        self,
        path: str,
        value: Any,
        validation_level: ConfigValidationLevel
    ) -> ConfigValidationResponse:
        """Validate a configuration update."""
        errors = []
        warnings = []
        
        # Check for restricted paths
        if path in self._restricted_paths and validation_level == ConfigValidationLevel.STRICT:
            warnings.append(self._restricted_paths[path])
        
        # Validate based on configuration type
        if "timeout" in path.lower() and isinstance(value, (int, float)):
            if value <= 0:
                errors.append("Timeout values must be positive")
            elif value > 300:  # 5 minutes
                warnings.append("Large timeout values may cause poor user experience")
        
        return ConfigValidationResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def mask_sensitive_values(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive values in configuration."""
        def mask_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "***MASKED***" if any(sensitive in k.lower() for sensitive in self._sensitive_keys)
                    else mask_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [mask_recursive(item) for item in obj]
            else:
                return obj
        
        result = mask_recursive(config_dict)
        return result if isinstance(result, dict) else config_dict

    def _validate_llm_config(self, llm_config: Dict[str, Any]) -> List[str]:
        """Validate LLM configuration and return warnings."""
        warnings = []
        
        if "openai" in llm_config:
            openai_config = llm_config["openai"]
            if not openai_config.get("api_key"):
                warnings.append("OpenAI API key not set - set OPENAI_API_KEY environment variable")
            
            model = openai_config.get("model_name", "")
            if "gpt-4" in model and "turbo" not in model:
                warnings.append("Using older GPT-4 model - consider upgrading to gpt-4-turbo")
        
        return warnings

    def _validate_database_config(self, db_config: Dict[str, Any]) -> List[str]:
        """Validate database configuration and return suggestions."""
        suggestions = []
        
        db_path = db_config.get("db_filename", "")
        if not db_path:
            suggestions.append("Consider setting a custom database path for data persistence")
        elif not db_path.endswith(".db"):
            suggestions.append("Database filename should end with .db extension")
        
        return suggestions

    def _set_nested_value(self, obj: Dict[str, Any], path: str, value: Any) -> None:
        """Set a nested value using dot notation."""
        parts = path.split('.')
        for part in parts[:-1]:
            obj = obj.setdefault(part, {})
        obj[parts[-1]] = value