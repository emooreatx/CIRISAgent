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
    
    # Discord configuration
    discord_id = get_env_var("DISCORD_CHANNEL_ID")
    if discord_id and not config.get("discord_channel_id"):
        config["discord_channel_id"] = discord_id
    
    # Runtime configuration
    log_level = get_env_var("LOG_LEVEL")
    if log_level and not config.get("log_level"):
        config["log_level"] = log_level
    
    # Database paths
    if "database" not in config:
        config["database"] = {}
    
    db_path = get_env_var("CIRIS_DB_PATH")
    if db_path and not config["database"].get("db_filename"):
        config["database"]["db_filename"] = db_path
    
    data_dir = get_env_var("CIRIS_DATA_DIR")
    if data_dir and not config["database"].get("data_directory"):
        config["database"]["data_directory"] = data_dir
    
    # Secrets configuration
    if "secrets" not in config:
        config["secrets"] = {}
    if "storage" not in config["secrets"]:
        config["secrets"]["storage"] = {}
    
    secrets_db = get_env_var("SECRETS_DB_PATH")
    if secrets_db and not config["secrets"]["storage"].get("database_path"):
        config["secrets"]["storage"]["database_path"] = secrets_db
    
    # Resource limits
    if "resources" not in config:
        config["resources"] = {}
    if "budgets" not in config["resources"]:
        config["resources"]["budgets"] = {}
    
    memory_limit = get_env_var("RESOURCE_MEMORY_LIMIT")
    if memory_limit and "memory" in config["resources"]["budgets"]:
        try:
            config["resources"]["budgets"]["memory"]["limit"] = float(memory_limit)
        except ValueError:
            pass
    
    cpu_limit = get_env_var("RESOURCE_CPU_LIMIT")
    if cpu_limit and "cpu" in config["resources"]["budgets"]:
        try:
            config["resources"]["budgets"]["cpu"]["limit"] = float(cpu_limit)
        except ValueError:
            pass
    
    # Telemetry configuration
    if "telemetry" not in config:
        config["telemetry"] = {}
    
    telemetry_enabled = get_env_var("TELEMETRY_ENABLED")
    if telemetry_enabled and not config["telemetry"].get("enabled"):
        config["telemetry"]["enabled"] = telemetry_enabled.lower() in ("true", "1", "yes")
    
    buffer_size = get_env_var("TELEMETRY_BUFFER_SIZE")
    if buffer_size and not config["telemetry"].get("buffer_size"):
        try:
            config["telemetry"]["buffer_size"] = int(buffer_size)
        except ValueError:
            pass
    
    # Audit configuration
    if "audit" not in config:
        config["audit"] = {}
    
    audit_log = get_env_var("AUDIT_LOG_PATH")
    if audit_log and not config["audit"].get("audit_log_path"):
        config["audit"]["audit_log_path"] = audit_log
    
    signed_audit = get_env_var("AUDIT_ENABLE_SIGNED")
    if signed_audit and not config["audit"].get("enable_signed_audit"):
        config["audit"]["enable_signed_audit"] = signed_audit.lower() in ("true", "1", "yes")
    
    # Circuit breaker configuration
    if "adaptive" not in config:
        config["adaptive"] = {}
    if "circuit_breaker" not in config["adaptive"]:
        config["adaptive"]["circuit_breaker"] = {}
    
    failure_threshold = get_env_var("CIRCUIT_BREAKER_FAILURE_THRESHOLD")
    if failure_threshold and not config["adaptive"]["circuit_breaker"].get("failure_threshold"):
        try:
            config["adaptive"]["circuit_breaker"]["failure_threshold"] = int(failure_threshold)
        except ValueError:
            pass
    
    # Archive configuration
    archive_dir = get_env_var("CIRIS_ARCHIVE_DIR")
    if archive_dir and not config.get("data_archive_dir"):
        config["data_archive_dir"] = archive_dir
    
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
        
        # Load environment variables for all configuration sections that support it
        app_config.llm_services.openai.load_env_vars()
        app_config.secrets.load_env_vars()
        app_config.cirisnode.load_env_vars()
        
        return app_config
