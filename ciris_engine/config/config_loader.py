import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from ciris_engine.schemas.config_schemas_v1 import AppConfig


def _deep_merge(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dictionaries."""
    for key, value in update.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            base[key] = _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


async def _load_yaml(path: Path) -> Dict[str, Any]:
    def _loader(p: Path) -> Dict[str, Any]:
        if not p.exists():
            return {}
        with open(p, "r") as f:
            return yaml.safe_load(f) or {}

    return await asyncio.to_thread(_loader, path)


def _load_env_config() -> Dict[str, Any]:
    env_config: Dict[str, Any] = {}
    discord_id = os.getenv("DISCORD_CHANNEL_ID")
    if discord_id:
        env_config["discord_channel_id"] = discord_id
    return env_config


def _merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for cfg in configs:
        merged = _deep_merge(merged, cfg)
    return merged


class ConfigLoader:
    """Load and validate configuration."""

    @staticmethod
    async def load_config(
        config_path: Optional[Path] = None,
        profile_name: str = "default",
    ) -> AppConfig:
        """Load config with profile overlay."""

        base_path = Path(config_path or "config/base.yaml")
        profile_path = Path("ciris_profiles") / f"{profile_name}.yaml"

        base_config = await _load_yaml(base_path)
        profile_config = await _load_yaml(profile_path)
        env_config = _load_env_config()

        merged = _merge_configs(base_config, profile_config, env_config)
        return AppConfig(**merged)
