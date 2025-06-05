import yaml
import logging
import asyncio
from pathlib import Path
from typing import Optional, Any, List

from ciris_engine.schemas.config_schemas_v1 import AgentProfile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_PATH = Path("ciris_profiles/default.yaml")


async def load_profile(profile_path: Optional[Path]) -> Optional[AgentProfile]:
    """Asynchronously load an agent profile from a YAML file.

    This coroutine should be awaited so file I/O does not block the event loop.

    Args:
        profile_path: Path to the YAML profile file.

    Returns:
        A SerializableAgentProfile instance if loading is successful, otherwise None.
    """
    if profile_path is None:
        profile_path = DEFAULT_PROFILE_PATH
    elif not isinstance(profile_path, Path):
        profile_path = Path(profile_path)

    if not profile_path.exists() or not profile_path.is_file():
        if profile_path != DEFAULT_PROFILE_PATH:
            logger.warning(
                f"Profile file {profile_path} not found. Falling back to default profile {DEFAULT_PROFILE_PATH}"
            )
            profile_path = DEFAULT_PROFILE_PATH
        if not profile_path.exists() or not profile_path.is_file():
            logger.error(f"Default profile file not found: {profile_path}")
            return None

    try:
        def _load_yaml(path: Path) -> Any:
            with open(path, "r") as f:
                return yaml.safe_load(f)

        profile_data = await asyncio.to_thread(_load_yaml, profile_path)
        
        if not profile_data:
            logger.error(f"Profile file is empty or invalid YAML: {profile_path}")
            return None
            
        # Ensure 'name' is present, as it's key for SerializableAgentProfile
        if 'name' not in profile_data:
            # Try to infer name from filename if not in YAML content
            profile_data['name'] = profile_path.stem 
            logger.warning(f"Profile 'name' not found in YAML, inferred as '{profile_data['name']}' from filename: {profile_path}")



        # Convert permitted_actions from string to HandlerActionType robustly
        if "permitted_actions" in profile_data:
            from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
            converted_actions: List[Any] = []
            for action in profile_data["permitted_actions"]:
                if isinstance(action, HandlerActionType):
                    converted_actions.append(action)
                elif isinstance(action, str):
                    try:
                        # Try to convert string to enum (case-insensitive value)
                        enum_action = HandlerActionType(action)
                        converted_actions.append(enum_action)
                    except ValueError:
                        try:
                            # Try by name (case-insensitive)
                            enum_action = HandlerActionType[action.upper()]
                            converted_actions.append(enum_action)
                        except KeyError:
                            # Try matching by lowercased value
                            matched = False
                            for member in HandlerActionType:
                                if member.value.lower() == action.lower():
                                    converted_actions.append(member)
                                    matched = True
                                    break
                            if not matched:
                                logger.warning(f"Unknown action '{action}' in permitted_actions, skipping")
                else:
                    logger.warning(f"Invalid action type {type(action)} in permitted_actions")
            # Ensure all are HandlerActionType, filter out any str
            profile_data["permitted_actions"] = [a for a in converted_actions if isinstance(a, HandlerActionType)]

        # The profile_data should directly map to SerializableAgentProfile fields
        profile = AgentProfile(**profile_data)
        logger.info(f"Successfully loaded profile '{profile.name}' from {profile_path}")
        return profile
        
    except yaml.YAMLError as e:
        logger.exception(f"Error parsing YAML profile file {profile_path}: {e}")
    except Exception as e:
        logger.exception(f"Error loading or validating profile from {profile_path}: {e}")
    
    return None
