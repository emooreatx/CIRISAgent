import yaml
import logging
from pathlib import Path
from typing import Optional

from ciris_engine.core.config_schemas import SerializableAgentProfile

logger = logging.getLogger(__name__)

def load_profile(profile_path: Path) -> Optional[SerializableAgentProfile]:
    """
    Loads an agent profile from a YAML file.

    Args:
        profile_path: Path to the YAML profile file.

    Returns:
        A SerializableAgentProfile instance if loading is successful, otherwise None.
    """
    if not isinstance(profile_path, Path):
        profile_path = Path(profile_path)

    if not profile_path.exists() or not profile_path.is_file():
        logger.error(f"Profile file not found or is not a file: {profile_path}")
        return None

    try:
        with open(profile_path, 'r') as f:
            profile_data = yaml.safe_load(f)
        
        if not profile_data:
            logger.error(f"Profile file is empty or invalid YAML: {profile_path}")
            return None
            
        # Ensure 'name' is present, as it's key for SerializableAgentProfile
        if 'name' not in profile_data:
            # Try to infer name from filename if not in YAML content
            profile_data['name'] = profile_path.stem 
            logger.warning(f"Profile 'name' not found in YAML, inferred as '{profile_data['name']}' from filename: {profile_path}")

        # The profile_data should directly map to SerializableAgentProfile fields
        profile = SerializableAgentProfile(**profile_data)
        logger.info(f"Successfully loaded profile '{profile.name}' from {profile_path}")
        return profile
        
    except yaml.YAMLError as e:
        logger.exception(f"Error parsing YAML profile file {profile_path}: {e}")
    except Exception as e:
        logger.exception(f"Error loading or validating profile from {profile_path}: {e}")
    
    return None
