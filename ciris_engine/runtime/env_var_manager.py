"""Environment variable management component for runtime config management."""
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable, List, Optional

from ciris_engine.schemas.runtime_control_schemas import EnvVarResponse

logger = logging.getLogger(__name__)


class EnvVarManager:
    """Handles environment variable management operations."""

    def __init__(self) -> None:
        """Initialize the environment variable manager."""
        self._env_file = Path(".env")

    async def set_env_var(
        self,
        name: str,
        value: str,
        persist: bool = False,
        reload_config_callback: Optional[Callable[[], Awaitable[None]]] = None
    ) -> EnvVarResponse:
        """Set an environment variable."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Set in current environment
            os.environ[name] = value
            
            # Persist to .env file if requested
            if persist:
                await self._persist_env_var(name, value)
            
            # Reload configuration if callback provided
            if reload_config_callback:
                await reload_config_callback()
            
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
        reload_config_callback: Optional[Callable[[], Awaitable[None]]] = None
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
            
            # Reload configuration if callback provided
            if reload_config_callback:
                await reload_config_callback()
            
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

    async def _persist_env_var(self, name: str, value: str) -> None:
        """Persist environment variable to .env file."""
        # Read existing content
        existing_lines = []
        if self._env_file.exists():
            with open(self._env_file, 'r') as f:
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
        with open(self._env_file, 'w') as f:
            f.writelines(existing_lines)

    async def _remove_from_env_file(self, name: str) -> None:
        """Remove environment variable from .env file."""
        if not self._env_file.exists():
            return
        
        # Read existing content
        with open(self._env_file, 'r') as f:
            lines = f.readlines()
        
        # Filter out the variable
        filtered_lines = [
            line for line in lines
            if not line.strip().startswith(f"{name}=")
        ]
        
        # Write back to file
        with open(self._env_file, 'w') as f:
            f.writelines(filtered_lines)

    def get_env_vars(self) -> List[tuple[str, str]]:
        """Get all environment variables from .env file."""
        env_vars = []
        if self._env_file.exists():
            with open(self._env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars.append((key.strip(), value.strip()))
        return env_vars