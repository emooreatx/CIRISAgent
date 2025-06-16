"""
Identity management for CIRIS Agent runtime.

Handles loading, creating, and persisting agent identity.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pathlib import Path
import hashlib

from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ciris_engine.schemas.identity_schemas_v1 import (
    AgentIdentityRoot,
    CoreProfile,
    IdentityMetadata
)

logger = logging.getLogger(__name__)


class IdentityManager:
    """Manages agent identity lifecycle."""
    
    def __init__(self, profile_name: str, config: Any):
        self.profile_name = profile_name
        self.config = config
        self.agent_identity: Optional[AgentIdentityRoot] = None
    
    async def initialize_identity(self) -> AgentIdentityRoot:
        """Initialize agent identity - create from profile on first run, load from graph thereafter."""
        # Check if identity exists in graph
        identity_data = await self._get_identity_from_graph()
        
        if identity_data:
            # Identity exists - load it and use it
            logger.info("Loading existing agent identity from graph")
            self.agent_identity = AgentIdentityRoot.model_validate(identity_data)
        else:
            # First run - use profile to create initial identity
            logger.info("No identity found, creating from profile (first run only)")
            
            # Load profile ONLY for initial identity creation
            profile_path = Path(self.config.profile_directory) / f"{self.profile_name}.yaml"
            initial_profile = await self._load_profile(profile_path)
            
            if not initial_profile:
                logger.warning(f"Profile '{self.profile_name}' not found, using default")
                default_path = Path(self.config.profile_directory) / "default.yaml"
                initial_profile = await self._load_profile(default_path)
                
            if not initial_profile:
                raise RuntimeError("No profile available for initial identity creation")
            
            # Create identity from profile and save to graph
            self.agent_identity = await self._create_identity_from_profile(initial_profile)
            await self._save_identity_to_graph(self.agent_identity)
        
        return self.agent_identity
    
    async def _load_profile(self, profile_path: Path) -> Optional[AgentProfile]:
        """Load profile from file."""
        from ciris_engine.utils.profile_loader import load_profile
        return await load_profile(profile_path)
    
    async def _get_identity_from_graph(self) -> Optional[Dict[str, Any]]:
        """Retrieve agent identity from the persistence tier."""
        try:
            from ciris_engine.persistence.models.identity import retrieve_agent_identity
            
            identity = await retrieve_agent_identity()
            if identity:
                return identity.model_dump()
                
        except Exception as e:
            logger.warning(f"Failed to retrieve identity from persistence: {e}")
        
        return None
    
    async def _save_identity_to_graph(self, identity: AgentIdentityRoot) -> None:
        """Save agent identity to the persistence tier."""
        try:
            from ciris_engine.persistence.models.identity import store_agent_identity
            
            success = await store_agent_identity(identity)
            if success:
                logger.info("Agent identity saved to persistence tier")
            else:
                raise RuntimeError("Failed to store agent identity")
                
        except Exception as e:
            logger.error(f"Failed to save identity to persistence: {e}")
            raise
    
    async def _create_identity_from_profile(self, profile: AgentProfile) -> AgentIdentityRoot:
        """Create initial identity from profile (first run only)."""
        # Generate deterministic identity hash
        identity_string = f"{profile.name}:{profile.description}:{profile.role_description}"
        identity_hash = hashlib.sha256(identity_string.encode()).hexdigest()
        
        # Extract DSDMA configuration from profile
        dsdma_kwargs = profile.dsdma_kwargs or {}
        domain_knowledge = dsdma_kwargs.get('domain_specific_knowledge', {})
        dsdma_prompt = dsdma_kwargs.get('prompt_template', None)
        
        # Create identity root from profile
        return AgentIdentityRoot(
            agent_id=profile.name,
            identity_hash=identity_hash,
            core_profile=CoreProfile(
                description=profile.description,
                role_description=profile.role_description,
                domain_specific_knowledge=domain_knowledge,
                dsdma_prompt_template=dsdma_prompt,
                csdma_overrides=profile.csdma_overrides or {},
                action_selection_pdma_overrides=profile.action_selection_pdma_overrides or {}
            ),
            identity_metadata=IdentityMetadata(
                created_at=datetime.now(timezone.utc).isoformat(),
                last_modified=datetime.now(timezone.utc).isoformat(),
                modification_count=0,
                creator_agent_id="system",
                lineage_trace=["system"],
                approval_required=True,
                approved_by=None,
                approval_timestamp=None
            ),
            allowed_capabilities=[
                "communication", "memory", "observation", "tool_use",
                "ethical_reasoning", "self_modification", "task_management"
            ],
            restricted_capabilities=[
                "identity_change_without_approval",
                "profile_switching",
                "unauthorized_data_access"
            ]
        )
    
    async def verify_identity_integrity(self) -> bool:
        """Verify identity has been properly loaded."""
        if not self.agent_identity:
            logger.error("No agent identity loaded")
            return False
        
        # Verify core fields
        required_fields = ['agent_id', 'identity_hash', 'core_profile']
        for field in required_fields:
            if not hasattr(self.agent_identity, field) or not getattr(self.agent_identity, field):
                logger.error(f"Identity missing required field: {field}")
                return False
        
        logger.info("✓ Agent identity verified")
        return True