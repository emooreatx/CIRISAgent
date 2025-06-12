"""Configuration management service for runtime control."""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ciris_engine.adapters.base import Service
from ciris_engine.config.config_manager import get_config
from ciris_engine.config.config_loader import ConfigLoader
from ciris_engine.config.dynamic_config import ConfigManager
from ciris_engine.config.env_utils import get_env_var
from ciris_engine.runtime.config_validator import ConfigValidator
from ciris_engine.runtime.profile_manager import ProfileManager
from ciris_engine.runtime.env_var_manager import EnvVarManager
from ciris_engine.runtime.config_backup_manager import ConfigBackupManager
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.schemas.runtime_control_schemas import (
    ConfigScope, ConfigValidationLevel, ConfigOperationResponse,
    ConfigValidationResponse, AgentProfileInfo, AgentProfileResponse,
    EnvVarResponse, ConfigBackupResponse
)

logger = logging.getLogger(__name__)


class ConfigManagerService(Service):
    """Service for managing configuration at runtime."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self._config_manager: Optional[ConfigManager] = None
        self._config_lock = asyncio.Lock()
        self._config_history: List[Dict[str, Any]] = []
        self._max_history = 100
        self._is_running = False
        
        # Initialize components
        self._validator = ConfigValidator()
        self._profile_manager = ProfileManager()
        self._env_var_manager = EnvVarManager()
        self._backup_manager = ConfigBackupManager()

    async def start(self) -> None:
        """Start the configuration manager service."""
        await super().start()
        try:
            current_config = get_config()
            self._config_manager = ConfigManager(current_config)
            self._is_running = True
            logger.info("Configuration manager service started")
        except Exception as e:
            logger.error(f"Failed to start config manager service: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the configuration manager service."""
        await super().stop()
        self._is_running = False
        logger.info("Configuration manager service stopped")
    
    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return self._is_running and self._config_manager is not None
    
    async def get_capabilities(self) -> List[str]:
        """Get service capabilities."""
        return [
            "config.get",
            "config.update", 
            "config.validate",
            "profile.list",
            "profile.create",
            "profile.reload",
            "env.set",
            "env.delete",
            "backup.create",
            "backup.restore"
        ]

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
                    config_dict = self._validator.mask_sensitive_values(config_dict)
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
                result = self._validator.mask_sensitive_values(result)
            
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
                    validation = await self._validator.validate_config_update(path, value, validation_level)
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
        return await self._validator.validate_config(
            config_data, 
            config_path,
            self.config_manager.config if config_path else None
        )

    # Agent Profile Operations
    async def list_profiles(self) -> List[AgentProfileInfo]:
        """List all available agent profiles."""
        return await self._profile_manager.list_profiles(self.config_manager.config)

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
                
                self._profile_manager.add_loaded_profile(profile_name)
                
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
        return await self._profile_manager.create_profile(
            name, config, description, base_profile, save_to_file
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
        callback = self._reload_config_with_env_vars if reload_config else None
        return await self._env_var_manager.set_env_var(name, value, persist, callback)

    async def delete_env_var(
        self,
        name: str,
        persist: bool = False,
        reload_config: bool = True
    ) -> EnvVarResponse:
        """Delete an environment variable."""
        callback = self._reload_config_with_env_vars if reload_config else None
        return await self._env_var_manager.delete_env_var(name, persist, callback)

    # Backup and Restore Operations
    async def backup_config(
        self,
        include_profiles: bool = True,
        include_env_vars: bool = False,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a backup of the current configuration."""
        return await self._backup_manager.backup_config(
            include_profiles, include_env_vars, backup_name
        )

    # Helper Methods

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


    async def _reload_config_with_env_vars(self) -> None:
        """Reload configuration to pick up environment variable changes."""
        try:
            # This would require reloading the configuration from environment variables
            # For now, we'll just log the action
            logger.info("Configuration reloaded with updated environment variables")
        except Exception as e:
            logger.error(f"Failed to reload config with env vars: {e}")


    def get_config_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get configuration change history."""
        return self._config_history[-limit:]

    def get_loaded_profiles(self) -> List[str]:
        """Get list of loaded profile names."""
        return self._profile_manager.get_loaded_profiles()
