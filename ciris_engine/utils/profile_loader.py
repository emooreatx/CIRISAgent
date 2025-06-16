import yaml
import logging
import asyncio
from pathlib import Path
from typing import Optional, Any, List

from ciris_engine.schemas.config_schemas_v1 import AgentProfile

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE_PATH = Path("ciris_templates/default.yaml")


async def load_template(template_path: Optional[Path]) -> Optional[AgentProfile]:
    """Asynchronously load an agent template from a YAML file.

    This coroutine should be awaited so file I/O does not block the event loop.

    Args:
        template_path: Path to the YAML template file.

    Returns:
        An AgentProfile instance if loading is successful, otherwise None.
    """
    if template_path is None:
        template_path = DEFAULT_TEMPLATE_PATH

    if not template_path.exists() or not template_path.is_file():
        if template_path != DEFAULT_TEMPLATE_PATH:
            logger.warning(
                f"Template file {template_path} not found. Falling back to default template {DEFAULT_TEMPLATE_PATH}"
            )
            template_path = DEFAULT_TEMPLATE_PATH
        if not template_path.exists() or not template_path.is_file():
            logger.error(f"Default template file not found: {template_path}")
            return None

    try:
        def _load_yaml(path: Path) -> Any:
            with open(path, "r") as f:
                return yaml.safe_load(f)

        template_data = await asyncio.to_thread(_load_yaml, template_path)
        
        if not template_data:
            logger.error(f"Template file is empty or invalid YAML: {template_path}")
            return None
            
        if 'name' not in template_data:
            template_data['name'] = template_path.stem 
            logger.warning(f"Template 'name' not found in YAML, inferred as '{template_data['name']}' from filename: {template_path}")



        if "permitted_actions" in template_data:
            from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
            converted_actions: List[Any] = []
            for action in template_data["permitted_actions"]:
                if isinstance(action, HandlerActionType):
                    converted_actions.append(action)
                elif isinstance(action, str):
                    try:
                        enum_action = HandlerActionType(action)
                        converted_actions.append(enum_action)
                    except ValueError:
                        try:
                            enum_action = HandlerActionType[action.upper()]
                            converted_actions.append(enum_action)
                        except KeyError:
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
            template_data["permitted_actions"] = [a for a in converted_actions if isinstance(a, HandlerActionType)]

        template = AgentProfile(**template_data)
        logger.info(f"Successfully loaded template '{template.name}' from {template_path}")
        return template
        
    except yaml.YAMLError as e:
        logger.exception(f"Error parsing YAML template file {template_path}: {e}")
    except Exception as e:
        logger.exception(f"Error loading or validating template from {template_path}: {e}")
    
    return None
