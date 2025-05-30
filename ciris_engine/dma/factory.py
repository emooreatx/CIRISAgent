import logging
from pathlib import Path
from typing import Dict, Optional, Type

from ciris_engine.registries.base import ServiceRegistry

from .dsdma_base import BaseDSDMA
from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ..utils.profile_loader import load_profile

logger = logging.getLogger(__name__)

# Registry of available DSDMA classes
DSDMA_CLASS_REGISTRY: Dict[str, Type[BaseDSDMA]] = {
    "BaseDSDMA": BaseDSDMA,
}

DEFAULT_PROFILE_PATH = Path("ciris_profiles/default.yaml")

async def create_dsdma_from_profile(
    profile: Optional[AgentProfile],
    service_registry: ServiceRegistry,
    *,
    model_name: Optional[str] = None,
    default_profile_path: Path = DEFAULT_PROFILE_PATH,
) -> Optional[BaseDSDMA]:
    """Instantiate a DSDMA based on the given profile.

    If ``profile`` is ``None`` or lacks ``dsdma_identifier``, the default profile
    from ``default_profile_path`` is loaded and used instead.
    """
    if profile is None or not profile.dsdma_identifier:
        logger.info(
            "No specific DSDMA profile provided; loading default profile from %s",
            default_profile_path,
        )
        profile = await load_profile(default_profile_path)
        if profile is None:
            logger.error("Default profile could not be loaded")
            return None

    dsdma_cls = DSDMA_CLASS_REGISTRY.get(profile.dsdma_identifier)
    if not dsdma_cls:
        logger.error("Unknown DSDMA identifier: %s", profile.dsdma_identifier)
        return None

    overrides = profile.dsdma_kwargs or {}
    prompt_template = overrides.get("prompt_template")
    domain_knowledge = overrides.get("domain_specific_knowledge")

    return dsdma_cls(
        domain_name=profile.name,
        service_registry=service_registry,
        model_name=model_name,
        domain_specific_knowledge=domain_knowledge,
        prompt_template=prompt_template,
    )
