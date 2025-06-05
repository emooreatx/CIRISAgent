import asyncio
from typing import Any, Callable
from pathlib import Path

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from .config_loader import ConfigLoader


class ConfigManager:
    """Manage runtime configuration changes."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._lock = asyncio.Lock()

    @property
    def config(self) -> AppConfig:
        return self._config

    async def watch_config_changes(self, callback: Callable[[AppConfig], None]) -> None:
        """Watch for config file changes.

        Placeholder implementation that simply invokes callback with the current
        configuration. Real file watching is out of scope for tests.
        """
        callback(self._config)

    async def update_config(self, path: str, value: Any) -> None:
        """Update configuration value at runtime."""
        async with self._lock:
            parts = path.split(".")
            obj = self._config
            for part in parts[:-1]:
                obj = getattr(obj, part)
            setattr(obj, parts[-1], value)

    async def reload_profile(self, profile_name: str, config_path: Path | None = None) -> None:
        """Hot-reload agent profile."""
        new_config = await ConfigLoader.load_config(config_path, profile_name)
        async with self._lock:
            self._config = new_config
