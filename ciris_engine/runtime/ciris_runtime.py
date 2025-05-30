"""
ciris_engine/runtime/ciris_runtime.py

New simplified runtime that properly orchestrates all components.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.processor import AgentProcessor
from ciris_engine.adapters.base import Service
from ciris_engine import persistence
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.adapters.openai_compatible_llm import OpenAICompatibleLLM
from ciris_engine.adapters import AuditService
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies

# Service Registry
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

# Components
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
from ciris_engine.context.builder import ContextBuilder
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher

# DMAs
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.dma.factory import create_dsdma_from_profile
from ciris_engine.guardrails import EthicalGuardrails

# IO Adapters
from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider, GraphQLClient

import instructor

logger = logging.getLogger(__name__)


class CIRISRuntime:
    """
    Main runtime orchestrator for CIRIS Agent.
    Handles initialization of all components and services.
    """
    
    def __init__(
        self,
        profile_name: str = "default",
        io_adapter: Optional[Any] = None,
        app_config: Optional[AppConfig] = None,
        startup_channel_id: Optional[str] = None,
    ):
        self.profile_name = profile_name
        self.io_adapter = io_adapter
        self.app_config = app_config
        self.startup_channel_id = startup_channel_id
        
        # Core services
        self.llm_service: Optional[OpenAICompatibleLLM] = None
        self.memory_service: Optional[LocalGraphMemoryService] = None
        self.audit_service: Optional[AuditService] = None
        self.maintenance_service: Optional[DatabaseMaintenanceService] = None
        
        # Service Registry
        self.service_registry: Optional[ServiceRegistry] = None
        
        # Multi-service sink for unified action routing
        self.multi_service_sink: Optional[MultiServiceActionSink] = None
        
        # Processor
        self.agent_processor: Optional[AgentProcessor] = None
        
        # Profile
        self.profile: Optional[AgentProfile] = None
        
        # Track initialization state
        self._initialized = False
        
    async def initialize(self):
        """Initialize all components and services."""
        if self._initialized:
            return
            
        logger.info(f"Initializing CIRIS Runtime with profile '{self.profile_name}'...")
        
        # 1. Initialize database
        persistence.initialize_database()
        
        # 2. Load configuration
        if not self.app_config:
            from ciris_engine.config.config_manager import get_config_async
            self.app_config = await get_config_async()
        
        # 3. Load profile
        await self._load_profile()
        
        # 4. Initialize services
        await self._initialize_services()
        
        # 5. Build components
        await self._build_components()
        
        # 6. Perform startup maintenance
        await self._perform_startup_maintenance()
        
        self._initialized = True
        logger.info("CIRIS Runtime initialized successfully")
        
    async def _load_profile(self):
        """Load the agent profile."""
        profile_path = Path(self.app_config.profile_directory) / f"{self.profile_name}.yaml"
        self.profile = await load_profile(profile_path)
        
        if not self.profile:
            # Try default profile
            logger.warning(f"Profile '{self.profile_name}' not found, loading default profile")
            default_path = Path(self.app_config.profile_directory) / "default.yaml"
            self.profile = await load_profile(default_path)
            
        if not self.profile:
            raise RuntimeError("No profile could be loaded")
            
        # Register profile in app_config
        self.app_config.agent_profiles[self.profile.name.lower()] = self.profile
        
        # Also load default as fallback if not already loaded
        if "default" not in self.app_config.agent_profiles:
            default_path = Path(self.app_config.profile_directory) / "default.yaml"
            default_profile = await load_profile(default_path)
            if default_profile:
                self.app_config.agent_profiles["default"] = default_profile
                
    async def _initialize_services(self):
        """Initialize all core services."""
        # Service Registry (initialize first)
        self.service_registry = ServiceRegistry()
        
        # Multi-service sink for action routing
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            max_queue_size=1000,
            fallback_channel_id=self.startup_channel_id
        )
        
        # LLM Service
        self.llm_service = OpenAICompatibleLLM(self.app_config.llm_services)
        await self.llm_service.start()
        
        # Memory Service
        self.memory_service = LocalGraphMemoryService()
        await self.memory_service.start()
        
        # Audit Service
        self.audit_service = AuditService()
        await self.audit_service.start()
        
        # Maintenance Service
        archive_dir = getattr(self.app_config, "data_archive_dir", "data_archive")
        archive_hours = getattr(self.app_config, "archive_older_than_hours", 24)
        self.maintenance_service = DatabaseMaintenanceService(
            archive_dir_path=archive_dir,
            archive_older_than_hours=archive_hours
        )
        
    async def _perform_startup_maintenance(self):
        """Perform database cleanup at startup."""
        if self.maintenance_service:
            await self.maintenance_service.perform_startup_cleanup()
            
    async def _build_components(self):
        """Build all processing components."""
        llm_client = self.llm_service.get_client()
        
        # Build DMAs
        ethical_pdma = EthicalPDMAEvaluator(
            aclient=llm_client.instruct_client,
            model_name=llm_client.model_name,
            max_retries=self.app_config.llm_services.openai.max_retries
        )
        
        csdma = CSDMAEvaluator(
            aclient=llm_client.client,
            model_name=llm_client.model_name,
            max_retries=self.app_config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.csdma_overrides if self.profile else None
        )
        
        action_pdma = ActionSelectionPDMAEvaluator(
            aclient=llm_client.client,
            model_name=llm_client.model_name,
            max_retries=self.app_config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.action_selection_pdma_overrides if self.profile else None,
            instructor_mode=instructor.Mode[self.app_config.llm_services.openai.instructor_mode.upper()]
        )
        
        # Create DSDMA
        dsdma = await create_dsdma_from_profile(
            self.profile,
            llm_client.client,
            model_name=llm_client.model_name
        )
        
        # Build guardrails
        guardrails = EthicalGuardrails(
            llm_client.instruct_client,
            self.app_config.guardrails,
            model_name=llm_client.model_name
        )
        
        # Build context provider
        graphql_provider = GraphQLContextProvider(
            graphql_client=GraphQLClient() if self.app_config.guardrails.enable_remote_graphql else None,
            memory_service=self.memory_service,
            enable_remote_graphql=self.app_config.guardrails.enable_remote_graphql
        )
        
        # Build orchestrators
        dma_orchestrator = DMAOrchestrator(
            ethical_pdma,
            csdma,
            dsdma,
            action_pdma,
            app_config=self.app_config,
            llm_service=self.llm_service,
            memory_service=self.memory_service
        )
        
        context_builder = ContextBuilder(
            memory_service=self.memory_service,
            graphql_provider=graphql_provider,
            app_config=self.app_config
        )
        
        guardrail_orchestrator = GuardrailOrchestrator(guardrails)
        
        # Register core services in the service registry
        await self._register_core_services()
        
        # Create dependencies for handlers and ThoughtProcessor
        dependencies = ActionHandlerDependencies(
            service_registry=self.service_registry,
            action_sink=self.multi_service_sink  # Use multi-service sink as primary action sink
        )
        
        # Build thought processor
        thought_processor = ThoughtProcessor(
            dma_orchestrator,
            context_builder,
            guardrail_orchestrator,
            self.app_config,
            dependencies
        )
        
        # Build action dispatcher - this needs to be customized per IO adapter
        action_dispatcher = await self._build_action_dispatcher(dependencies)
        
        # Update dependencies with action_sink from the action dispatcher
        # The action_sink should be set by the subclass implementation of _build_action_dispatcher
        
        # Build agent processor
        self.agent_processor = AgentProcessor(
            app_config=self.app_config,
            active_profile=self.profile,  # Pass the active profile
            thought_processor=thought_processor,
            action_dispatcher=action_dispatcher,
            services={
                "llm_service": self.llm_service,
                "memory_service": self.memory_service,
                "audit_service": self.audit_service,
                "service_registry": self.service_registry,
                "io_adapter": self.io_adapter,
            },
            startup_channel_id=self.startup_channel_id,
        )
        
    async def _register_core_services(self):
        """Register core services in the service registry."""
        if not self.service_registry:
            return
        
        # Register memory service for all handlers that need memory operations
        if self.memory_service:
            # Register for all major handlers
            handler_names = [
                "MemorizeHandler", "RecallHandler", "ForgetHandler",
                "SpeakHandler", "ToolHandler", "ObserveHandler"
            ]
            
            for handler_name in handler_names:
                self.service_registry.register(
                    handler=handler_name,
                    service_type="memory",
                    provider=self.memory_service,
                    priority=Priority.HIGH,
                    capabilities=["memorize", "recall", "forget"]
                )
        
        # Register audit service globally for all handlers
        if self.audit_service:
            self.service_registry.register_global(
                service_type="audit",
                provider=self.audit_service,
                priority=Priority.HIGH,
                capabilities=["log_action", "get_audit_trail"]
            )
        
        # Note: Communication and WA services will be registered by subclasses
        # (e.g., DiscordRuntime registers Discord adapter, CIRISNode client)
        
    async def _build_action_dispatcher(self, dependencies):
        """Build action dispatcher. Override in subclasses for custom sinks."""
        # This is a basic implementation - subclasses should override
        # to provide proper action_sink, deferral_sink, etc.
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_ponder_rounds=self.app_config.workflow.max_ponder_rounds,
            action_sink=None,  # Override in subclass
            memory_service=self.memory_service,
        )
        
    async def run(self, max_rounds: Optional[int] = None):
        """Run the agent processing loop."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Start multi-service sink processing
            if self.multi_service_sink:
                await self.multi_service_sink.start()
            
            # Start IO adapter
            await self.io_adapter.start()
            
            # Start processing
            await self.agent_processor.start_processing(num_rounds=max_rounds)
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
        finally:
            await self.shutdown()
            
    async def shutdown(self):
        """Gracefully shutdown all services."""
        logger.info("Shutting down CIRIS Runtime...")
        
        # Stop processor
        if self.agent_processor:
            await self.agent_processor.stop_processing()
            
        # Stop multi-service sink
        if self.multi_service_sink:
            await self.multi_service_sink.stop()
            
        # Stop IO adapter
        if self.io_adapter:
            await self.io_adapter.stop()
            
        # Stop services
        services_to_stop = [
            self.llm_service,
            self.memory_service,
            self.audit_service,
            self.maintenance_service,
        ]
        
        await asyncio.gather(
            *[s.stop() for s in services_to_stop if s],
            return_exceptions=True
        )
        
        # Clear service registry
        if self.service_registry:
            self.service_registry.clear_all()
            self.service_registry = None
        
        logger.info("CIRIS Runtime shutdown complete")