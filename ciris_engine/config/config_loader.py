import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, TYPE_CHECKING
import yaml

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentTemplate
from .env_utils import get_env_var

if TYPE_CHECKING:
    from ciris_engine.adapters.discord.config import DiscordAdapterConfig
    from ciris_engine.adapters.api.config import APIAdapterConfig
    from ciris_engine.adapters.cli.config import CLIAdapterConfig


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
    
    
    log_level = get_env_var("LOG_LEVEL")
    if log_level and not config.get("log_level"):
        config["log_level"] = log_level
    
    if "database" not in config:
        config["database"] = {}
    
    db_path = get_env_var("CIRIS_DB_PATH")
    if db_path and not config["database"].get("db_filename"):
        config["database"]["db_filename"] = db_path
    
    data_dir = get_env_var("CIRIS_DATA_DIR")
    if data_dir and not config["database"].get("data_directory"):
        config["database"]["data_directory"] = data_dir
    
    if "secrets" not in config:
        config["secrets"] = {}
    if "storage" not in config["secrets"]:
        config["secrets"]["storage"] = {}
    
    secrets_db = get_env_var("SECRETS_DB_PATH")
    if secrets_db and not config["secrets"]["storage"].get("database_path"):
        config["secrets"]["storage"]["database_path"] = secrets_db
    
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
    
    if "audit" not in config:
        config["audit"] = {}
    
    audit_log = get_env_var("AUDIT_LOG_PATH")
    if audit_log and not config["audit"].get("audit_log_path"):
        config["audit"]["audit_log_path"] = audit_log
    
    signed_audit = get_env_var("AUDIT_ENABLE_SIGNED")
    if signed_audit and not config["audit"].get("enable_signed_audit"):
        config["audit"]["enable_signed_audit"] = signed_audit.lower() in ("true", "1", "yes")
    
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
        template_name: str = "default",
    ) -> AppConfig:
        """Load config with template overlay."""

        base_path = Path(config_path or "config/base.yaml")
        template_overlay_path = Path("ciris_templates") / f"{template_name}.yaml"

        base_config_data = await _load_yaml(base_path)
        template_data = await _load_yaml(template_overlay_path)
        
        base_config_data = _apply_env_defaults(base_config_data)
        
        app_config = AppConfig(**base_config_data)
        
        if hasattr(app_config, 'llm_services') and hasattr(app_config.llm_services, 'openai') and hasattr(app_config.llm_services.openai, 'load_env_vars'):
            app_config.llm_services.openai.load_env_vars()
        if hasattr(app_config, 'secrets') and hasattr(app_config.secrets, 'load_env_vars'):
            app_config.secrets.load_env_vars()
        if hasattr(app_config, 'cirisnode') and hasattr(app_config.cirisnode, 'load_env_vars'):
            app_config.cirisnode.load_env_vars()

        active_template = None
        if template_data:
            # Check if this looks like an agent template definition
            is_agent_template = 'name' in template_data or any(key in template_data for key in ['dsdma_kwargs', 'permitted_actions', 'discord_config', 'api_config', 'cli_config'])
            
            # First, merge any config overrides from the template
            config_overrides = {k: v for k, v in template_data.items() 
                              if k not in ['name', 'description', 'role_description', 'dsdma_kwargs', 
                                         'permitted_actions', 'discord_config', 'api_config', 'cli_config']}
            
            if config_overrides:
                merged_data = _merge_configs(base_config_data, config_overrides)
                app_config = AppConfig(**merged_data)
            
            # Then handle agent template creation if applicable
            if is_agent_template:
                from ciris_engine.adapters.discord.config import DiscordAdapterConfig
                
                if 'discord_config' in template_data:
                    discord_config = DiscordAdapterConfig(**template_data['discord_config'])
                else:
                    discord_config = DiscordAdapterConfig()
                
                discord_config.load_env_vars()
                # Convert to dict for proper validation
                template_data['discord_config'] = discord_config.model_dump()
                
                active_template = AgentTemplate(**template_data)
                app_config.agent_templates[template_name] = active_template

        
        return app_config
