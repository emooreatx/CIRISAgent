import os
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from ciris_engine.schemas.config_schemas_v1 import AppConfig
from .env_utils import get_env_var


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


def _apply_env_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Fill missing config fields from environment variables."""
    discord_id = get_env_var("DISCORD_CHANNEL_ID")
    if discord_id and not config.get("discord_channel_id"):
        config["discord_channel_id"] = discord_id
    return config


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
        merged = _merge_configs(base_config, profile_config)
        merged = _apply_env_defaults(merged)
        
        app_config = AppConfig(**merged)
        
        app_config.llm_services.openai.load_env_vars()
        
        return app_config
