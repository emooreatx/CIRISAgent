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
from ciris_engine.utils.constants import DEFAULT_NUM_ROUNDS

from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.adapters.openai_compatible_llm import OpenAICompatibleLLM
from ciris_engine.adapters import AuditService
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService
from .runtime_interface import RuntimeInterface
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.utils.shutdown_manager import (
    get_shutdown_manager, 
    register_global_shutdown_handler,
    wait_for_global_shutdown,
    is_global_shutdown_requested
)

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
from ciris_engine.guardrails import (
    GuardrailRegistry,
    EntropyGuardrail,
    CoherenceGuardrail,
    OptimizationVetoGuardrail,
    EpistemicHumilityGuardrail,
)

# IO Adapters
from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider, GraphQLClient

import instructor

logger = logging.getLogger(__name__)


class CIRISRuntime(RuntimeInterface):
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
    ) -> None:
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
        
        # Shutdown mechanism
        self._shutdown_event = asyncio.Event()
        self._shutdown_reason: Optional[str] = None
        self._shutdown_manager = get_shutdown_manager()
        
        # Track initialization state
        self._initialized = False
    
    def _ensure_config(self) -> AppConfig:
        """Ensure app_config is available, raise if not."""
        if not self.app_config:
            raise RuntimeError("App config not initialized")
        return self.app_config
    
    def request_shutdown(self, reason: str = "Shutdown requested") -> None:
        """Request a graceful shutdown of the runtime."""
        if self._shutdown_event.is_set():
            logger.debug(f"Shutdown already requested, ignoring duplicate request: {reason}")
            return
        
        logger.critical(f"RUNTIME SHUTDOWN REQUESTED: {reason}")
        self._shutdown_reason = reason
        self._shutdown_event.set()
        
        # Also notify the global shutdown manager
        self._shutdown_manager.request_shutdown(f"Runtime: {reason}")

    async def _request_shutdown(self, reason: str = "Shutdown requested") -> None:
        """Async wrapper used during initialization failures."""
        self.request_shutdown(reason)
        
    async def initialize(self) -> None:
        """Initialize all components and services."""
        if self._initialized:
            return
            
        logger.info(f"Initializing CIRIS Runtime with profile '{self.profile_name}'...")
        
        try:
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
            
            # 6. Perform startup maintenance (CRITICAL - failure triggers shutdown)
            await self._perform_startup_maintenance()
            
            self._initialized = True
            logger.info("CIRIS Runtime initialized successfully")
            
        except Exception as e:
            logger.critical(f"Runtime initialization failed: {e}")
            if "maintenance" in str(e).lower():
                logger.critical("Database maintenance failure during initialization - system cannot start safely")
            # Re-raise to prevent the runtime from starting with an inconsistent state
            raise
        
    async def _load_profile(self) -> None:
        """Load the agent profile."""
        config = self._ensure_config()
            
        profile_path = Path(config.profile_directory) / f"{self.profile_name}.yaml"
        self.profile = await load_profile(profile_path)
        
        if not self.profile:
            # Try default profile
            logger.warning(f"Profile '{self.profile_name}' not found, loading default profile")
            default_path = Path(config.profile_directory) / "default.yaml"
            self.profile = await load_profile(default_path)
            
        if not self.profile:
            raise RuntimeError("No profile could be loaded")
            
        # Register profile in app_config
        config.agent_profiles[self.profile.name.lower()] = self.profile
        
        # Also load default as fallback if not already loaded
        if "default" not in config.agent_profiles:
            default_path = Path(config.profile_directory) / "default.yaml"
            default_profile = await load_profile(default_path)
            if default_profile:
                config.agent_profiles["default"] = default_profile
                
    async def _initialize_services(self) -> None:
        """Initialize all core services."""
        # Service Registry (initialize first)
        self.service_registry = ServiceRegistry()
        
        # Multi-service sink for action routing
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            max_queue_size=1000,
            fallback_channel_id=self.startup_channel_id,
        )
        
        # LLM Service
        config = self._ensure_config()
        self.llm_service = OpenAICompatibleLLM(config.llm_services)
        await self.llm_service.start()
        
        # Memory Service
        self.memory_service = LocalGraphMemoryService()
        await self.memory_service.start()
        
        # Audit Service
        self.audit_service = AuditService()
        await self.audit_service.start()
        
        # Maintenance Service
        archive_dir = getattr(config, "data_archive_dir", "data_archive")
        archive_hours = getattr(config, "archive_older_than_hours", 24)
        self.maintenance_service = DatabaseMaintenanceService(
            archive_dir_path=archive_dir,
            archive_older_than_hours=archive_hours
        )
        
    async def _perform_startup_maintenance(self) -> None:
        """Perform database cleanup at startup."""
        if self.maintenance_service:
            try:
                logger.info("Starting critical database maintenance...")
                await self.maintenance_service.perform_startup_cleanup()
                logger.info("Database maintenance completed successfully")
            except Exception as e:
                logger.critical(f"CRITICAL ERROR: Database maintenance failed during startup: {e}")
                logger.critical("Database integrity cannot be guaranteed - initiating graceful shutdown")
                await self._request_shutdown(f"Critical database maintenance failure: {e}")
                raise RuntimeError(f"Database maintenance failure: {e}") from e
        else:
            logger.critical("CRITICAL ERROR: No maintenance service available during startup")
            logger.critical("Database integrity cannot be guaranteed - initiating graceful shutdown")
            await self._request_shutdown("No maintenance service available")
            raise RuntimeError("No maintenance service available")



            
    async def _build_components(self) -> None:
        """Build all processing components."""
        if not self.llm_service:
            raise RuntimeError("LLM service not initialized")
            
        config = self._ensure_config()
        llm_client = self.llm_service.get_client()

        # Build DMAs using service registry
        ethical_pdma = EthicalPDMAEvaluator(
            service_registry=self.service_registry,
            model_name=llm_client.model_name,
            max_retries=config.llm_services.openai.max_retries,
        )

        csdma = CSDMAEvaluator(
            service_registry=self.service_registry,
            model_name=llm_client.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.csdma_overrides if self.profile else None,
        )

        action_pdma = ActionSelectionPDMAEvaluator(
            service_registry=self.service_registry,
            model_name=llm_client.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.action_selection_pdma_overrides if self.profile else None,
            instructor_mode=instructor.Mode[config.llm_services.openai.instructor_mode.upper()],
        )

        # Create DSDMA
        dsdma = await create_dsdma_from_profile(
            self.profile,
            self.service_registry,
            model_name=llm_client.model_name,
        )
        
        # Build guardrails
        guardrail_registry = GuardrailRegistry()
        guardrail_registry.register_guardrail(
            "entropy",
            EntropyGuardrail(self.service_registry, config.guardrails, llm_client.model_name),
            priority=0,
        )
        guardrail_registry.register_guardrail(
            "coherence",
            CoherenceGuardrail(self.service_registry, config.guardrails, llm_client.model_name),
            priority=1,
        )
        guardrail_registry.register_guardrail(
            "optimization_veto",
            OptimizationVetoGuardrail(self.service_registry, config.guardrails, llm_client.model_name),
            priority=2,
        )
        guardrail_registry.register_guardrail(
            "epistemic_humility",
            EpistemicHumilityGuardrail(self.service_registry, config.guardrails, llm_client.model_name),
            priority=3,
        )
        
        # Build context provider
        graphql_provider = GraphQLContextProvider(
            graphql_client=GraphQLClient() if config.guardrails.enable_remote_graphql else None,
            memory_service=self.memory_service,
            enable_remote_graphql=config.guardrails.enable_remote_graphql
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
        
        guardrail_orchestrator = GuardrailOrchestrator(guardrail_registry)
        
        # Register core services in the service registry
        await self._register_core_services()
        
        # Create dependencies for handlers and ThoughtProcessor
        dependencies = ActionHandlerDependencies(
            service_registry=self.service_registry,
            io_adapter=self.io_adapter,
            shutdown_callback=lambda: self.request_shutdown(
                "Handler requested shutdown due to critical service failure"
            ),
        )
        # Set additional services as attributes (previously handled by **legacy_services)
        dependencies.multi_service_sink = self.multi_service_sink
        dependencies.memory_service = self.memory_service
        dependencies.audit_service = self.audit_service
        
        # Register runtime shutdown with global manager
        register_global_shutdown_handler(
            lambda: self.request_shutdown("Global shutdown manager triggered"),
            is_async=False
        )
        
        # Build thought processor
        if not self.app_config:
            raise RuntimeError("AppConfig is required for ThoughtProcessor initialization")
        thought_processor = ThoughtProcessor(
            dma_orchestrator,
            context_builder,
            guardrail_orchestrator,
            self.app_config,
            dependencies
        )
        
        # Build action dispatcher - this needs to be customized per IO adapter
        action_dispatcher = await self._build_action_dispatcher(dependencies)
        

        
        # Build agent processor
        if not self.app_config:
            raise RuntimeError("AppConfig is required for AgentProcessor initialization")
        if not self.profile:
            raise RuntimeError("Profile is required for AgentProcessor initialization")
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
        
    async def _register_core_services(self) -> None:
        """Register core services in the service registry."""
        if not self.service_registry:
            return
        
        # Register memory service for all handlers that need memory operations
        if self.memory_service:
            # Register for all major handlers
            handler_names = [
                "MemorizeHandler", "RecallHandler", "ForgetHandler",
                "SpeakHandler", "ToolHandler", "ObserveHandler", "TaskCompleteHandler"
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

        # Register LLM service globally so processors and DMAs can fetch it
        if self.llm_service:
            self.service_registry.register_global(
                service_type="llm",
                provider=self.llm_service,
                priority=Priority.HIGH,
                capabilities=["generate_response", "generate_structured_response"]
            )
        
        # Note: Communication and WA services will be registered by subclasses
        # (e.g., DiscordRuntime registers Discord adapter, CIRISNode client)
        
    async def _build_action_dispatcher(self, dependencies: Any) -> Any:
        """Build action dispatcher. Override in subclasses for custom sinks."""
        # This is a basic implementation - subclasses should override
        config = self._ensure_config()
        return build_action_dispatcher(
            service_registry=self.service_registry,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=config.workflow.max_rounds,
        )
        
    async def run(self, num_rounds: Optional[int] = None) -> None:
        """Run the agent processing loop with shutdown monitoring."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Start multi-service sink processing as background task
            if self.multi_service_sink:
                sink_task = asyncio.create_task(self.multi_service_sink.start())
                logger.info("Started multi-service sink as background task")

            
            # Start IO adapter
            if self.io_adapter:
                await self.io_adapter.start()
                logger.info("Started IO adapter")
            
            # Start processing and monitor for shutdown requests
            if not self.agent_processor:
                raise RuntimeError("Agent processor not initialized")
                
            # Use the provided num_rounds, or fall back to DEFAULT_NUM_ROUNDS (None = infinite)
            effective_num_rounds = num_rounds if num_rounds is not None else DEFAULT_NUM_ROUNDS
            logger.info("Starting agent processing with WAKEUP sequence...")
            processing_task = asyncio.create_task(
                self.agent_processor.start_processing(effective_num_rounds)
            )
            shutdown_task = asyncio.create_task(self._shutdown_event.wait())
            global_shutdown_task = asyncio.create_task(wait_for_global_shutdown())
            
            # Wait for either processing to complete or shutdown to be requested
            done, pending = await asyncio.wait(
                [processing_task, shutdown_task, global_shutdown_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel any remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if shutdown was requested
            if self._shutdown_event.is_set() or is_global_shutdown_requested():
                if self._shutdown_reason:
                    logger.critical(f"GRACEFUL SHUTDOWN TRIGGERED: {self._shutdown_reason}")
                elif is_global_shutdown_requested():
                    logger.critical(f"GLOBAL SHUTDOWN TRIGGERED: {self._shutdown_manager.get_shutdown_reason()}")
                else:
                    logger.critical("GRACEFUL SHUTDOWN TRIGGERED: Unknown reason")
                    
                # Execute any pending global shutdown handlers
                await self._shutdown_manager.execute_async_handlers()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
        finally:
            await self.shutdown()
            
    async def shutdown(self) -> None:
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
