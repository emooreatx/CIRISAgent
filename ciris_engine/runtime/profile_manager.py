"""Agent profile management component for runtime config management."""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from ciris_engine.schemas.config_schemas_v1 import AgentProfile, AppConfig
from ciris_engine.schemas.runtime_control_schemas import (
    AgentProfileInfo,
    AgentProfileResponse,
)
from ciris_engine.utils.profile_loader import load_profile

logger = logging.getLogger(__name__)


class ProfileManager:
    """Handles agent profile management operations."""

    def __init__(self) -> None:
        """Initialize the profile manager."""
        self._profiles_dir = Path("ciris_profiles")
        self._loaded_profiles: set[str] = set()

    async def list_profiles(self, current_config: Optional[AppConfig] = None) -> List[AgentProfileInfo]:
        """List all available agent profiles."""
        try:
            profiles = []
            
            if self._profiles_dir.exists():
                for profile_file in self._profiles_dir.glob("*.yaml"):
                    profile_name = profile_file.stem
                    try:
                        # Load profile to get info
                        profile = await load_profile(profile_file)
                        
                        # Get file stats
                        stat = profile_file.stat()
                        
                        # Check if this profile is currently active
                        is_active = False
                        if current_config:
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
                base_profile_path = self._profiles_dir / f"{base_profile}.yaml"
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
            profile_path = None
            if save_to_file:
                self._profiles_dir.mkdir(exist_ok=True)
                profile_path = self._profiles_dir / f"{name}.yaml"
                
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

    def add_loaded_profile(self, profile_name: str) -> None:
        """Track a loaded profile."""
        self._loaded_profiles.add(profile_name)

    def get_loaded_profiles(self) -> List[str]:
        """Get list of loaded profile names."""
        return list(self._loaded_profiles)

    async def _load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load YAML file asynchronously."""
        def _sync_load() -> Dict[str, Any]:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        
        return await asyncio.to_thread(_sync_load)