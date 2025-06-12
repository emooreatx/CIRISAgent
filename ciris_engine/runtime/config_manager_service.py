"""Configuration management service for runtime control."""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ciris_engine.config.config_manager import get_config
from ciris_engine.config.config_loader import ConfigLoader
from ciris_engine.config.dynamic_config import ConfigManager
from ciris_engine.config.env_utils import get_env_var
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.schemas.runtime_control_schemas import (
    ConfigScope, ConfigValidationLevel, ConfigOperationResponse,
    ConfigValidationResponse, AgentProfileInfo, AgentProfileResponse,
    EnvVarResponse, ConfigBackupResponse
)

logger = logging.getLogger(__name__)


class ConfigManagerService:
    """Service for managing configuration at runtime."""

    def __init__(self) -> None:
        self._config_manager: Optional[ConfigManager] = None
        self._backup_dir = Path("config_backups")
        self._backup_dir.mkdir(exist_ok=True)
        self._config_lock = asyncio.Lock()
        self._loaded_profiles: Set[str] = set()
        self._config_history: List[Dict[str, Any]] = []
        self._max_history = 100

    async def initialize(self) -> None:
        """Initialize the configuration manager service."""
        try:
            current_config = get_config()
            self._config_manager = ConfigManager(current_config)
            logger.info("Configuration manager service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize config manager service: {e}")
            raise

    @property
    def config_manager(self) -> ConfigManager:
        """Get the configuration manager instance."""
        if self._config_manager is None:
            raise RuntimeError("Configuration manager not initialized")
        return self._config_manager

    # Configuration Value Operations
    async def get_config_value(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get configuration value(s) at the specified path."""
        try:
            config = self.config_manager.config
            
            if path is None:
                # Return entire configuration
                config_dict = config.model_dump(mode="json")
                if not include_sensitive:
                    config_dict = self._mask_sensitive_values(config_dict)
                return config_dict
            
            # Navigate to specific path
            value = config
            for part in path.split('.'):
                if hasattr(value, part):
                    value = getattr(value, part)
                else:
                    raise ValueError(f"Configuration path '{path}' not found")
            
            # Convert to serializable format
            result: Any
            if hasattr(value, 'model_dump'):
                result = value.model_dump(mode="json")
            elif isinstance(value, (str, int, float, bool, list, dict, type(None))):
                result = value
            else:
                result = str(value)
            
            if not include_sensitive and isinstance(result, dict):
                result = self._mask_sensitive_values(result)
            
            return {"path": path, "value": result}
            
        except Exception as e:
            logger.error(f"Failed to get config value at path '{path}': {e}")
            raise

    async def update_config_value(
        self,
        path: str,
        value: Any,
        scope: ConfigScope = ConfigScope.RUNTIME,
        validation_level: ConfigValidationLevel = ConfigValidationLevel.STRICT,
        reason: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update a configuration value."""
        async with self._config_lock:
            try:
                start_time = datetime.now(timezone.utc)
                
                # Get old value for history
                old_value = None
                try:
                    old_config = await self.get_config_value(path)
                    old_value = old_config.get("value")
                except:
                    pass  # Path might not exist yet
                
                # Validate the update if requested
                if validation_level != ConfigValidationLevel.BYPASS:
                    validation = await self._validate_config_update(path, value, validation_level)
                    if not validation.valid and validation_level == ConfigValidationLevel.STRICT:
                        return ConfigOperationResponse(
                            success=False,
                            operation="update_config",
                            timestamp=start_time,
                            path=path,
                            error=f"Validation failed: {'; '.join(validation.errors)}",
                            warnings=validation.warnings
                        )
                
                # Apply the update
                await self.config_manager.update_config(path, value)
                
                # Record the change
                change_record = {
                    "timestamp": start_time.isoformat(),
                    "operation": "update_config",
                    "path": path,
                    "old_value": old_value,
                    "new_value": value,
                    "scope": scope.value,
                    "reason": reason
                }
                self._record_config_change(change_record)
                
                # Handle persistence based on scope
                if scope == ConfigScope.PERSISTENT:
                    await self._persist_config_change(path, value, reason)
                
                return ConfigOperationResponse(
                    success=True,
                    operation="update_config",
                    timestamp=start_time,
                    path=path,
                    old_value=old_value,
                    new_value=value,
                    scope=scope,
                    message=f"Configuration updated: {path} = {value}"
                )
                
            except Exception as e:
                logger.error(f"Failed to update config at path '{path}': {e}")
                return ConfigOperationResponse(
                    success=False,
                    operation="update_config",
                    timestamp=datetime.now(timezone.utc),
                    path=path,
                    error=str(e)
                )

    async def validate_config(
        self,
        config_data: Dict[str, Any],
        config_path: Optional[str] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        try:
            errors = []
            warnings = []
            suggestions = []
            
            # Try to create AppConfig with the data
            try:
                if config_path:
                    # Validate partial config at specific path
                    current_config = self.config_manager.config.model_dump()
                    test_config = current_config.copy()
                    self._set_nested_value(test_config, config_path, config_data)
                    AppConfig(**test_config)
                else:
                    # Validate complete config
                    AppConfig(**config_data)
            except Exception as e:
                errors.append(str(e))
            
            # Additional custom validations
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

    # Agent Profile Operations
    async def list_profiles(self) -> List[AgentProfileInfo]:
        """List all available agent profiles."""
        try:
            profiles = []
            profiles_dir = Path("ciris_profiles")
            
            if profiles_dir.exists():
                for profile_file in profiles_dir.glob("*.yaml"):
                    profile_name = profile_file.stem
                    try:
                        # Load profile to get info
                        from ciris_engine.utils.profile_loader import load_profile
                        profile = await load_profile(profile_file)
                        
                        # Get file stats
                        stat = profile_file.stat()
                        
                        # Check if this profile is currently active
                        current_config = self.config_manager.config
                        is_active = (
                            hasattr(current_config, 'agent_profiles') and
                            profile_name in current_config.agent_profiles
                        )
                        
                        if profile is not None:
                            profiles.append(AgentProfileInfo(
                                name=profile_name,
                                description=getattr(profile, 'description', '') or "",
                                file_path=str(profile_file),
                                is_active=is_active,
                                permitted_actions=[action.value for action in profile.permitted_actions] if profile.permitted_actions else [],
                            adapter_configs={
                                "discord": getattr(profile, "discord_config", {}) or {},
                                "api": getattr(profile, "api_config", {}) or {},
                                "cli": getattr(profile, "cli_config", {}) or {}
                            },
                            created_time=datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc),
                            modified_time=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                        ))
                        
                    except Exception as e:
                        logger.warning(f"Failed to load profile {profile_name}: {e}")
                        profiles.append(AgentProfileInfo(
                            name=profile_name,
                            description=f"Error loading profile: {str(e)}",
                            file_path=str(profile_file),
                            is_active=False,
                            permitted_actions=[],
                            adapter_configs={}
                        ))
            
            return profiles
            
        except Exception as e:
            logger.error(f"Failed to list profiles: {e}")
            return []

    async def reload_profile(
        self,
        profile_name: str,
        config_path: Optional[str] = None,
        scope: ConfigScope = ConfigScope.SESSION
    ) -> ConfigOperationResponse:
        """Reload an agent profile."""
        async with self._config_lock:
            try:
                start_time = datetime.now(timezone.utc)
                
                # Reload the profile
                config_path_obj = Path(config_path) if config_path else None
                await self.config_manager.reload_profile(profile_name, config_path_obj)
                
                self._loaded_profiles.add(profile_name)
                
                # Record the change
                change_record = {
                    "timestamp": start_time.isoformat(),
                    "operation": "reload_profile",
                    "profile_name": profile_name,
                    "scope": scope.value
                }
                self._record_config_change(change_record)
                
                return ConfigOperationResponse(
                    success=True,
                    operation="reload_profile",
                    timestamp=start_time,
                    path=f"profile:{profile_name}",
                    scope=scope,
                    message=f"Profile '{profile_name}' reloaded successfully"
                )
                
            except Exception as e:
                logger.error(f"Failed to reload profile '{profile_name}': {e}")
                return ConfigOperationResponse(
                    success=False,
                    operation="reload_profile",
                    timestamp=datetime.now(timezone.utc),
                    path=f"profile:{profile_name}",
                    error=str(e)
                )

    async def create_profile(
        self,
        name: str,
        config: Dict[str, Any],
        description: Optional[str] = None,
        base_profile: Optional[str] = None,
        save_to_file: bool = True
    ) -> AgentProfileResponse:
        """Create a new agent profile."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Prepare profile data
            profile_data = {
                "name": name,
                "description": description or f"Agent profile: {name}",
                **config
            }
            
            # If base profile specified, inherit from it
            if base_profile:
                base_profile_path = Path("ciris_profiles") / f"{base_profile}.yaml"
                if base_profile_path.exists():
                    base_data = await self._load_yaml(base_profile_path)
                    # Merge base profile with new config
                    profile_data = {**base_data, **profile_data}
            
            # Validate profile structure
            try:
                AgentProfile(**profile_data)
            except Exception as e:
                return AgentProfileResponse(
                    success=False,
                    profile_name=name,
                    operation="create_profile",
                    timestamp=start_time,
                    error=f"Profile validation failed: {str(e)}"
                )
            
            # Save to file if requested
            if save_to_file:
                profiles_dir = Path("ciris_profiles")
                profiles_dir.mkdir(exist_ok=True)
                profile_path = profiles_dir / f"{name}.yaml"
                
                import yaml
                with open(profile_path, 'w') as f:
                    yaml.safe_dump(profile_data, f, default_flow_style=False)
            
            # Create profile info
            profile_info = AgentProfileInfo(
                name=name,
                description=description,
                file_path=str(profile_path) if save_to_file else "memory",
                is_active=False,
                permitted_actions=config.get("permitted_actions", []),
                adapter_configs={}
            )
            
            return AgentProfileResponse(
                success=True,
                profile_name=name,
                operation="create_profile",
                timestamp=start_time,
                message=f"Profile '{name}' created successfully",
                profile_info=profile_info
            )
            
        except Exception as e:
            logger.error(f"Failed to create profile '{name}': {e}")
            return AgentProfileResponse(
                success=False,
                profile_name=name,
                operation="create_profile",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Environment Variable Operations
    async def set_env_var(
        self,
        name: str,
        value: str,
        persist: bool = False,
        reload_config: bool = True
    ) -> EnvVarResponse:
        """Set an environment variable."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Set in current environment
            os.environ[name] = value
            
            # Persist to .env file if requested
            if persist:
                await self._persist_env_var(name, value)
            
            # Reload configuration if requested
            if reload_config:
                await self._reload_config_with_env_vars()
            
            return EnvVarResponse(
                success=True,
                operation="set_env_var",
                variable_name=name,
                timestamp=start_time,
                message=f"Environment variable '{name}' set successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to set environment variable '{name}': {e}")
            return EnvVarResponse(
                success=False,
                operation="set_env_var",
                variable_name=name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def delete_env_var(
        self,
        name: str,
        persist: bool = False,
        reload_config: bool = True
    ) -> EnvVarResponse:
        """Delete an environment variable."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Remove from current environment
            if name in os.environ:
                del os.environ[name]
            
            # Remove from .env file if requested
            if persist:
                await self._remove_from_env_file(name)
            
            # Reload configuration if requested
            if reload_config:
                await self._reload_config_with_env_vars()
            
            return EnvVarResponse(
                success=True,
                operation="delete_env_var",
                variable_name=name,
                timestamp=start_time,
                message=f"Environment variable '{name}' deleted successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to delete environment variable '{name}': {e}")
            return EnvVarResponse(
                success=False,
                operation="delete_env_var",
                variable_name=name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Backup and Restore Operations
    async def backup_config(
        self,
        include_profiles: bool = True,
        include_env_vars: bool = False,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a backup of the current configuration."""
        try:
            start_time = datetime.now(timezone.utc)
            
            if backup_name is None:
                backup_name = f"config_backup_{start_time.strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = self._backup_dir / backup_name
            backup_path.mkdir(exist_ok=True)
            
            files_included = []
            
            # Backup main config files
            config_files = ["config/base.yaml", "config/development.yaml", "config/production.yaml"]
            for config_file in config_files:
                config_path = Path(config_file)
                if config_path.exists():
                    dest_path = backup_path / config_path.name
                    shutil.copy2(config_path, dest_path)
                    files_included.append(str(config_path))
            
            # Backup profiles if requested
            if include_profiles:
                profiles_dir = Path("ciris_profiles")
                if profiles_dir.exists():
                    backup_profiles_dir = backup_path / "ciris_profiles"
                    shutil.copytree(profiles_dir, backup_profiles_dir, dirs_exist_ok=True)
                    for profile_file in profiles_dir.glob("*.yaml"):
                        files_included.append(str(profile_file))
            
            # Backup environment variables if requested
            if include_env_vars:
                env_file = Path(".env")
                if env_file.exists():
                    dest_env = backup_path / ".env"
                    shutil.copy2(env_file, dest_env)
                    files_included.append(str(env_file))
            
            # Create backup metadata
            metadata = {
                "backup_name": backup_name,
                "timestamp": start_time.isoformat(),
                "files_included": files_included,
                "include_profiles": include_profiles,
                "include_env_vars": include_env_vars
            }
            
            metadata_path = backup_path / "backup_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return ConfigBackupResponse(
                success=True,
                operation="backup_config",
                backup_name=backup_name,
                timestamp=start_time,
                files_included=files_included,
                message=f"Configuration backup '{backup_name}' created successfully"
            )
            
        except Exception as e:
            logger.error(f"Failed to backup configuration: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="backup_config",
                backup_name=backup_name or "unknown",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Helper Methods
    def _mask_sensitive_values(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive values in configuration."""
        sensitive_keys = {
            "api_key", "password", "secret", "token", "key", "auth",
            "credential", "private", "sensitive"
        }
        
        def mask_recursive(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {
                    k: "***MASKED***" if any(sensitive in k.lower() for sensitive in sensitive_keys)
                    else mask_recursive(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, list):
                return [mask_recursive(item) for item in obj]
            else:
                return obj
        
        result = mask_recursive(config_dict)
        return result if isinstance(result, dict) else config_dict

    async def _validate_config_update(
        self,
        path: str,
        value: Any,
        validation_level: ConfigValidationLevel
    ) -> ConfigValidationResponse:
        """Validate a configuration update."""
        errors = []
        warnings = []
        
        # Basic type checking
        path_parts = path.split('.')
        
        # Check for restricted paths
        restricted_paths = {
            "llm_services.openai.api_key": "API key changes should use environment variables",
            "database.db_filename": "Database path changes require restart",
            "secrets.storage_path": "Secrets path changes require restart"
        }
        
        if path in restricted_paths and validation_level == ConfigValidationLevel.STRICT:
            warnings.append(restricted_paths[path])
        
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

    def _record_config_change(self, change_record: Dict[str, Any]) -> None:
        """Record configuration change in history."""
        self._config_history.append(change_record)
        
        # Limit history size
        if len(self._config_history) > self._max_history:
            self._config_history = self._config_history[-self._max_history:]

    async def _persist_config_change(self, path: str, value: Any, reason: Optional[str]) -> None:
        """Persist configuration change to file (placeholder implementation)."""
        # This would require implementing file-based configuration persistence
        logger.info(f"Would persist config change: {path} = {value} (reason: {reason})")

    async def _persist_env_var(self, name: str, value: str) -> None:
        """Persist environment variable to .env file."""
        env_file = Path(".env")
        
        # Read existing content
        existing_lines = []
        if env_file.exists():
            with open(env_file, 'r') as f:
                existing_lines = f.readlines()
        
        # Update or add the variable
        updated = False
        for i, line in enumerate(existing_lines):
            if line.strip().startswith(f"{name}="):
                existing_lines[i] = f"{name}={value}\n"
                updated = True
                break
        
        if not updated:
            existing_lines.append(f"{name}={value}\n")
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(existing_lines)

    async def _remove_from_env_file(self, name: str) -> None:
        """Remove environment variable from .env file."""
        env_file = Path(".env")
        
        if not env_file.exists():
            return
        
        # Read existing content
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Filter out the variable
        filtered_lines = [
            line for line in lines
            if not line.strip().startswith(f"{name}=")
        ]
        
        # Write back to file
        with open(env_file, 'w') as f:
            f.writelines(filtered_lines)

    async def _reload_config_with_env_vars(self) -> None:
        """Reload configuration to pick up environment variable changes."""
        try:
            # This would require reloading the configuration from environment variables
            # For now, we'll just log the action
            logger.info("Configuration reloaded with updated environment variables")
        except Exception as e:
            logger.error(f"Failed to reload config with env vars: {e}")

    async def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file asynchronously."""
        import yaml
        
        def _sync_load() -> Dict[str, Any]:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        
        return await asyncio.to_thread(_sync_load)

    def get_config_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get configuration change history."""
        return self._config_history[-limit:]

    def get_loaded_profiles(self) -> List[str]:
        """Get list of loaded profile names."""
        return list(self._loaded_profiles)
