"""
Component builder for CIRIS Agent runtime.

Handles the construction of all processing components.
"""
import logging
from typing import Optional, Any

from ciris_engine.processor import AgentProcessor
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
from ciris_engine.context.builder import ContextBuilder
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.dma.factory import create_dsdma_from_profile
from ciris_engine.guardrails import (
    GuardrailRegistry,
    EntropyGuardrail,
    CoherenceGuardrail,
    OptimizationVetoGuardrail,
    EpistemicHumilityGuardrail,
)

from ciris_engine.faculties.faculty_manager import FacultyManager
from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider, GraphQLClient
from ciris_engine.utils.shutdown_manager import register_global_shutdown_handler

logger = logging.getLogger(__name__)


class ComponentBuilder:
    """Builds all processing components for the runtime."""
    
    def __init__(self, runtime: Any):
        """
        Initialize component builder.
        
        Args:
            runtime: Reference to the main runtime for access to services and config
        """
        self.runtime = runtime
        self.agent_processor: Optional[AgentProcessor] = None
    
    async def build_all_components(self) -> AgentProcessor:
        """Build all processing components and return the agent processor."""
        if not self.runtime.llm_service:
            raise RuntimeError("LLM service not initialized")
        
        if not self.runtime.service_registry:
            raise RuntimeError("Service registry not initialized")
            
        config = self.runtime._ensure_config()

        # Build DMAs
        ethical_pdma = EthicalPDMAEvaluator(
            service_registry=self.runtime.service_registry,
            model_name=self.runtime.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            sink=self.runtime.multi_service_sink,
        )

        # Get overrides from agent identity
        csdma_overrides = None
        if self.runtime.agent_identity and hasattr(self.runtime.agent_identity, 'core_profile'):
            csdma_overrides = self.runtime.agent_identity.core_profile.csdma_overrides
            
        csdma = CSDMAEvaluator(
            service_registry=self.runtime.service_registry,
            model_name=self.runtime.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=csdma_overrides,
            sink=self.runtime.multi_service_sink,
        )

        # Create faculty manager and epistemic faculties
        faculty_manager = FacultyManager(self.runtime.service_registry)
        faculty_manager.create_default_faculties()
        
        # Get action selection overrides from agent identity
        action_selection_overrides = None
        if self.runtime.agent_identity and hasattr(self.runtime.agent_identity, 'core_profile'):
            action_selection_overrides = self.runtime.agent_identity.core_profile.action_selection_pdma_overrides
            
        action_pdma = ActionSelectionPDMAEvaluator(
            service_registry=self.runtime.service_registry,
            model_name=self.runtime.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=action_selection_overrides,
            sink=self.runtime.multi_service_sink,
            faculties=faculty_manager.faculties,  # Pass faculties for enhanced evaluation
        )

        # Create DSDMA using agent's identity-based profile
        # The identity contains all the necessary overrides from the initial profile template
        if not self.runtime.agent_identity:
            raise RuntimeError("Cannot create DSDMA - no agent identity loaded from graph!")
            
        # Create a temporary profile object from identity for DSDMA creation
        # This bridges between the identity system and the DSDMA factory
        from ciris_engine.schemas.config_schemas_v1 import AgentProfile
        identity_as_profile = AgentProfile(
            name=self.runtime.agent_identity.agent_id,
            description=self.runtime.agent_identity.core_profile.description,
            role_description=self.runtime.agent_identity.core_profile.role_description,
            dsdma_kwargs={
                "domain_specific_knowledge": getattr(self.runtime.agent_identity.core_profile, 'domain_specific_knowledge', {}),
                "prompt_template": getattr(self.runtime.agent_identity.core_profile, 'dsdma_prompt_template', None)
            },
            csdma_overrides=self.runtime.agent_identity.core_profile.csdma_overrides,
            action_selection_pdma_overrides=self.runtime.agent_identity.core_profile.action_selection_pdma_overrides
        )
        
        dsdma = await create_dsdma_from_profile(
            identity_as_profile,
            self.runtime.service_registry,
            model_name=self.runtime.llm_service.model_name,
            sink=self.runtime.multi_service_sink,
        )
        
        # Build guardrails
        guardrail_registry = GuardrailRegistry()
        guardrail_registry.register_guardrail(
            "entropy",
            EntropyGuardrail(self.runtime.service_registry, config.guardrails, self.runtime.llm_service.model_name, self.runtime.multi_service_sink),
            priority=0,
        )
        guardrail_registry.register_guardrail(
            "coherence",
            CoherenceGuardrail(self.runtime.service_registry, config.guardrails, self.runtime.llm_service.model_name, self.runtime.multi_service_sink),
            priority=1,
        )
        guardrail_registry.register_guardrail(
            "optimization_veto",
            OptimizationVetoGuardrail(self.runtime.service_registry, config.guardrails, self.runtime.llm_service.model_name, self.runtime.multi_service_sink),
            priority=2,
        )
        guardrail_registry.register_guardrail(
            "epistemic_humility",
            EpistemicHumilityGuardrail(self.runtime.service_registry, config.guardrails, self.runtime.llm_service.model_name, self.runtime.multi_service_sink),
            priority=3,
        )
        
        # Build context provider
        graphql_provider = GraphQLContextProvider(
            graphql_client=GraphQLClient() if config.guardrails.enable_remote_graphql else None,
            memory_service=self.runtime.memory_service,
            enable_remote_graphql=config.guardrails.enable_remote_graphql
        )
        
        # Build orchestrators
        dma_orchestrator = DMAOrchestrator(
            ethical_pdma,
            csdma,
            dsdma,
            action_pdma,
            app_config=self.runtime.app_config,
            llm_service=self.runtime.llm_service,
            memory_service=self.runtime.memory_service
        )
        
        context_builder = ContextBuilder(
            memory_service=self.runtime.memory_service,
            graphql_provider=graphql_provider,
            app_config=self.runtime.app_config,
            telemetry_service=self.runtime.telemetry_service
        )
        
        guardrail_orchestrator = GuardrailOrchestrator(guardrail_registry)
        
        # Register core services before building action dispatcher
        await self.runtime._register_core_services()
        
        # Build action handler dependencies
        dependencies = ActionHandlerDependencies(
            service_registry=self.runtime.service_registry,
            shutdown_callback=lambda: self.runtime.request_shutdown(
                "Handler requested shutdown due to critical service failure"
            ),
            multi_service_sink=self.runtime.multi_service_sink,
            memory_service=self.runtime.memory_service,
            audit_service=self.runtime.audit_service,
        )
        
        # Register global shutdown handler
        register_global_shutdown_handler(
            lambda: self.runtime.request_shutdown("Global shutdown manager triggered"),
            is_async=False
        )
        
        # Build thought processor
        if not self.runtime.app_config:
            raise RuntimeError("AppConfig is required for ThoughtProcessor initialization")
            
        thought_processor = ThoughtProcessor(
            dma_orchestrator,
            context_builder,
            guardrail_orchestrator,
            self.runtime.app_config,
            dependencies,
            telemetry_service=self.runtime.telemetry_service
        )
        
        # Build action dispatcher
        action_dispatcher = await self._build_action_dispatcher(dependencies)
        
        # Build agent processor
        if not self.runtime.app_config:
            raise RuntimeError("AppConfig is required for AgentProcessor initialization")
        if not self.runtime.profile:
            raise RuntimeError("Profile is required for AgentProcessor initialization")
            
        self.agent_processor = AgentProcessor(
            app_config=self.runtime.app_config,
            profile=self.runtime.profile,
            thought_processor=thought_processor,
            action_dispatcher=action_dispatcher,
            services={
                "llm_service": self.runtime.llm_service,
                "memory_service": self.runtime.memory_service,
                "audit_service": self.runtime.audit_service,
                "service_registry": self.runtime.service_registry,
            },
            startup_channel_id=self.runtime.startup_channel_id,
            runtime=self.runtime,  # Pass runtime reference for preload tasks
        )
        
        return self.agent_processor
    
    async def _build_action_dispatcher(self, dependencies: Any) -> Any:
        """Build action dispatcher. Override in subclasses for custom sinks."""
        config = self.runtime._ensure_config()
        return build_action_dispatcher(
            service_registry=self.runtime.service_registry,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=config.workflow.max_rounds,
            telemetry_service=self.runtime.telemetry_service,
            multi_service_sink=self.runtime.multi_service_sink,
        )