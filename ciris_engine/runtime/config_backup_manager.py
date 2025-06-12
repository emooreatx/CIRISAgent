"""Configuration backup management component for runtime config management."""
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ciris_engine.schemas.runtime_control_schemas import ConfigBackupResponse

logger = logging.getLogger(__name__)


class ConfigBackupManager:
    """Handles configuration backup and restore operations."""

    def __init__(self, backup_dir: Optional[Path] = None) -> None:
        """Initialize the backup manager."""
        self._backup_dir = backup_dir or Path("config_backups")
        self._backup_dir.mkdir(exist_ok=True)

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

    async def restore_config(
        self,
        backup_name: str,
        restore_profiles: bool = True,
        restore_env_vars: bool = False
    ) -> ConfigBackupResponse:
        """Restore configuration from a backup."""
        try:
            start_time = datetime.now(timezone.utc)
            backup_path = self._backup_dir / backup_name
            
            if not backup_path.exists():
                return ConfigBackupResponse(
                    success=False,
                    operation="restore_config",
                    backup_name=backup_name,
                    timestamp=start_time,
                    error=f"Backup '{backup_name}' not found"
                )
            
            # Read backup metadata
            metadata_path = backup_path / "backup_metadata.json"
            if not metadata_path.exists():
                return ConfigBackupResponse(
                    success=False,
                    operation="restore_config",
                    backup_name=backup_name,
                    timestamp=start_time,
                    error="Backup metadata not found"
                )
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            files_restored = []
            
            # Restore main config files
            for config_file in ["base.yaml", "development.yaml", "production.yaml"]:
                src_path = backup_path / config_file
                if src_path.exists():
                    dest_path = Path("config") / config_file
                    dest_path.parent.mkdir(exist_ok=True)
                    shutil.copy2(src_path, dest_path)
                    files_restored.append(str(dest_path))
            
            # Restore profiles if requested
            if restore_profiles and metadata.get("include_profiles"):
                backup_profiles_dir = backup_path / "ciris_profiles"
                if backup_profiles_dir.exists():
                    profiles_dir = Path("ciris_profiles")
                    profiles_dir.mkdir(exist_ok=True)
                    for profile_file in backup_profiles_dir.glob("*.yaml"):
                        dest_file = profiles_dir / profile_file.name
                        shutil.copy2(profile_file, dest_file)
                        files_restored.append(str(dest_file))
            
            # Restore environment variables if requested
            if restore_env_vars and metadata.get("include_env_vars"):
                src_env = backup_path / ".env"
                if src_env.exists():
                    dest_env = Path(".env")
                    shutil.copy2(src_env, dest_env)
                    files_restored.append(str(dest_env))
            
            return ConfigBackupResponse(
                success=True,
                operation="restore_config",
                backup_name=backup_name,
                timestamp=start_time,
                files_included=files_restored,
                message=f"Configuration restored from backup '{backup_name}'"
            )
            
        except Exception as e:
            logger.error(f"Failed to restore configuration: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="restore_config",
                backup_name=backup_name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    def list_backups(self) -> List[dict[str, Any]]:
        """List all available backups."""
        backups = []
        for backup_dir in self._backup_dir.iterdir():
            if backup_dir.is_dir():
                metadata_path = backup_dir / "backup_metadata.json"
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        backups.append(metadata)
        return sorted(backups, key=lambda x: x.get('timestamp', ''), reverse=True)