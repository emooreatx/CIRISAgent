import logging
from pathlib import Path
from typing import Dict, Optional, Type, Any

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.dma_interface import (
    EthicalDMAInterface,
    CSDMAInterface,
    ActionSelectionDMAInterface,
)
from ciris_engine.protocols.faculties import EpistemicFaculty

from .dsdma_base import BaseDSDMA
from .moderation_dsdma import ModerationDSDMA
from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ..utils.profile_loader import load_profile

logger = logging.getLogger(__name__)

DSDMA_CLASS_REGISTRY: Dict[str, Type[BaseDSDMA]] = {
    "BaseDSDMA": BaseDSDMA,
    "ModerationDSDMA": ModerationDSDMA,
}

ETHICAL_DMA_REGISTRY: Dict[str, Type[EthicalDMAInterface]] = {}
CSDMA_REGISTRY: Dict[str, Type[CSDMAInterface]] = {}
ACTION_SELECTION_DMA_REGISTRY: Dict[str, Type[ActionSelectionDMAInterface]] = {}

try:
    from .pdma import EthicalPDMAEvaluator
    ETHICAL_DMA_REGISTRY["EthicalPDMAEvaluator"] = EthicalPDMAEvaluator
except ImportError:
    pass

try:
    from .csdma import CSDMAEvaluator
    CSDMA_REGISTRY["CSDMAEvaluator"] = CSDMAEvaluator
except ImportError:
    pass

try:
    from .action_selection_pdma import ActionSelectionPDMAEvaluator
    ACTION_SELECTION_DMA_REGISTRY["ActionSelectionPDMAEvaluator"] = ActionSelectionPDMAEvaluator
except ImportError:
    pass

DEFAULT_PROFILE_PATH = Path("ciris_profiles/default.yaml")

async def create_dma(
    dma_type: str,
    dma_identifier: str,
    service_registry: ServiceRegistry,
    *,
    model_name: Optional[str] = None,
    prompt_overrides: Optional[Dict[str, str]] = None,
    faculties: Optional[Dict[str, EpistemicFaculty]] = None,
    **kwargs: Any
) -> Any:
    """Create a DMA instance of the specified type.
    
    Args:
        dma_type: Type of DMA ('ethical', 'csdma', 'dsdma', 'action_selection')
        dma_identifier: Specific DMA class identifier
        service_registry: Service registry for dependencies
        model_name: Optional LLM model name
        prompt_overrides: Optional prompt customizations
        faculties: Optional epistemic faculties
        **kwargs: Additional DMA-specific parameters
        
    Returns:
        DMA instance or None if creation fails
    """
    registries = {
        'ethical': ETHICAL_DMA_REGISTRY,
        'csdma': CSDMA_REGISTRY,
        'dsdma': DSDMA_CLASS_REGISTRY,
        'action_selection': ACTION_SELECTION_DMA_REGISTRY,
    }
    
    registry = registries.get(dma_type)
    if not registry:
        logger.error(f"Unknown DMA type: {dma_type}")
        return None
        
    dma_class = registry.get(dma_identifier)  # type: ignore[attr-defined]
    if not dma_class:
        logger.error(f"Unknown {dma_type} DMA identifier: {dma_identifier}")
        return None
        
    try:
        constructor_args = {
            'service_registry': service_registry,
            **kwargs
        }
        
        if model_name is not None:
            constructor_args['model_name'] = model_name
        if prompt_overrides is not None:
            constructor_args['prompt_overrides'] = prompt_overrides  
        if faculties is not None:
            constructor_args['faculties'] = faculties
        
        return dma_class(**constructor_args)
    except Exception as e:
        logger.error(f"Failed to create {dma_type} DMA {dma_identifier}: {e}")
        return None

async def create_dsdma_from_profile(
    profile: Optional[AgentProfile],
    service_registry: ServiceRegistry,
    *,
    model_name: Optional[str] = None,
    default_profile_path: Path = DEFAULT_PROFILE_PATH,
    sink: Optional[Any] = None,
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

    if not profile.dsdma_identifier:
        logger.error("Profile has no dsdma_identifier")
        return None
    
    dsdma_cls = DSDMA_CLASS_REGISTRY.get(profile.dsdma_identifier)
    if not dsdma_cls:
        logger.error("Unknown DSDMA identifier: %s", profile.dsdma_identifier)
        return None

    overrides = profile.dsdma_kwargs or {}
    prompt_template = overrides.get("prompt_template")
    domain_knowledge = overrides.get("domain_specific_knowledge")

    dma_result = await create_dma(
        dma_type='dsdma',
        dma_identifier=profile.dsdma_identifier,
        service_registry=service_registry,
        model_name=model_name,
        prompt_overrides=None,
        domain_name=profile.name,
        domain_specific_knowledge=domain_knowledge,
        prompt_template=prompt_template,
        sink=sink,
    )
    
    # Ensure we return the correct type
    if isinstance(dma_result, BaseDSDMA):
        return dma_result
    
    logger.error(f"create_dma returned unexpected type: {type(dma_result)}")
    return None
