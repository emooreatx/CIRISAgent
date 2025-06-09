"""
ciris_engine/runtime/ciris_runtime.py

New simplified runtime that properly orchestrates all components.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.processor import AgentProcessor
from ciris_engine.adapters.base import Service
from ciris_engine import persistence
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.utils.constants import DEFAULT_NUM_ROUNDS
from ciris_engine.adapters import load_adapter
from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration

from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.adapters.openai_compatible_llm import OpenAICompatibleLLM
from ciris_engine.adapters import AuditService
from ciris_engine.adapters.signed_audit_service import SignedAuditService
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService
from .runtime_interface import RuntimeInterface
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.utils.shutdown_manager import (
    get_shutdown_manager, 
    register_global_shutdown_handler,
    wait_for_global_shutdown,
    is_global_shutdown_requested
)

from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, MemoryService
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink

from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
from ciris_engine.context.builder import ContextBuilder
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher

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
from ciris_engine.telemetry import TelemetryService, SecurityFilter
from ciris_engine.services.adaptive_filter_service import AdaptiveFilterService
from ciris_engine.services.agent_config_service import AgentConfigService
from ciris_engine.services.multi_service_transaction_orchestrator import MultiServiceTransactionOrchestrator
from ciris_engine.secrets.service import SecretsService

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
        modes: List[str],
        profile_name: str = "default",
        app_config: Optional[AppConfig] = None,
        startup_channel_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.profile_name = profile_name
        self.app_config = app_config
        self.startup_channel_id = startup_channel_id
        self.adapters: List[PlatformAdapter] = []

        for mode in modes:
            try:
                adapter_class = load_adapter(mode)
                self.adapters.append(adapter_class(self, **kwargs))
                logger.info(f"Successfully loaded and initialized adapter for mode: {mode}")
            except Exception as e:
                logger.error(f"Failed to load or initialize adapter for mode '{mode}': {e}", exc_info=True)
                # Depending on desired behavior, you might want to raise here or just log and continue
                # For now, let's log and continue, allowing other adapters to load.
        
        self.llm_service: Optional[OpenAICompatibleLLM] = None
        self.memory_service: Optional[LocalGraphMemoryService] = None
        self.audit_service: Optional[AuditService] = None
        self.maintenance_service: Optional[DatabaseMaintenanceService] = None
        self.telemetry_service: Optional[TelemetryService] = None
        self.secrets_service: Optional[SecretsService] = None
        self.adaptive_filter_service: Optional[AdaptiveFilterService] = None
        self.agent_config_service: Optional[AgentConfigService] = None
        self.transaction_orchestrator: Optional[MultiServiceTransactionOrchestrator] = None
        
        self.service_registry: Optional[ServiceRegistry] = None
        
        self.multi_service_sink: Optional[MultiServiceActionSink] = None
        
        self.agent_processor: Optional[AgentProcessor] = None
        
        self.profile: Optional[AgentProfile] = None
        
        self._shutdown_event: Optional[asyncio.Event] = None
        self._shutdown_reason: Optional[str] = None
        self._shutdown_manager = get_shutdown_manager()
        
        self._initialized = False
    
    def _ensure_shutdown_event(self) -> None:
        """Ensure shutdown event is created when needed in async context."""
        if self._shutdown_event is None:
            try:
                self._shutdown_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create shutdown event outside of async context")
    
    def _ensure_config(self) -> AppConfig:
        """Ensure app_config is available, raise if not."""
        if not self.app_config:
            raise RuntimeError("App config not initialized")
        return self.app_config
    
    def request_shutdown(self, reason: str = "Shutdown requested") -> None:
        """Request a graceful shutdown of the runtime."""
        self._ensure_shutdown_event()
        
        if self._shutdown_event and self._shutdown_event.is_set():
            logger.debug(f"Shutdown already requested, ignoring duplicate request: {reason}")
            return
        
        logger.critical(f"RUNTIME SHUTDOWN REQUESTED: {reason}")
        self._shutdown_reason = reason
        
        if self._shutdown_event:
            self._shutdown_event.set()
        
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
            persistence.initialize_database()
            
            if not self.app_config:
                from ciris_engine.config.config_manager import get_config_async
                self.app_config = await get_config_async()
            
            await self._load_profile()
            
            await self._initialize_services() # Core services

            await self._register_adapter_services() # Adapter-provided services
            
            await self._build_components() # Agent processor and its dependencies
            
            await self._perform_startup_maintenance()

            # Start adapters after core components are ready but before agent processor starts full operation
            await asyncio.gather(*(adapter.start() for adapter in self.adapters))
            logger.info(f"All {len(self.adapters)} adapters started.")
            
            self._initialized = True
            logger.info("CIRIS Runtime initialized successfully")
            
        except Exception as e:
            logger.critical(f"Runtime initialization failed: {e}", exc_info=True)
            if "maintenance" in str(e).lower():
                logger.critical("Database maintenance failure during initialization - system cannot start safely")
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
        self.service_registry = ServiceRegistry()
        
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            max_queue_size=1000,
            fallback_channel_id=self.startup_channel_id,
        )
        
        config = self._ensure_config()
        
        # Initialize telemetry service first so other services can use it
        self.telemetry_service = TelemetryService(
            buffer_size=1000,
            security_filter=SecurityFilter()
        )
        await self.telemetry_service.start()
        
        # Initialize LLM service with telemetry
        self.llm_service = OpenAICompatibleLLM(config.llm_services, telemetry_service=self.telemetry_service)
        await self.llm_service.start()
        
        self.memory_service = LocalGraphMemoryService()
        await self.memory_service.start()
        
        # Initialize audit service based on configuration
        if config.audit.enable_signed_audit:
            self.audit_service = SignedAuditService(
                log_path=config.audit.audit_log_path,
                db_path=config.audit.audit_db_path,
                key_path=config.audit.audit_key_path,
                rotation_size_mb=config.audit.rotation_size_mb,
                retention_days=config.audit.retention_days,
                enable_jsonl=config.audit.enable_jsonl_audit,
                enable_signed=config.audit.enable_signed_audit
            )
        else:
            self.audit_service = AuditService(
                log_path=config.audit.audit_log_path,
                rotation_size_mb=config.audit.rotation_size_mb,
                retention_days=config.audit.retention_days
            )
        await self.audit_service.start()
        
        # Initialize secrets service
        self.secrets_service = SecretsService(
            db_path=getattr(config.secrets, 'db_path', 'secrets.db') if hasattr(config, 'secrets') else 'secrets.db'
        )
        await self.secrets_service.start()
        
        # Initialize adaptive filter service
        self.adaptive_filter_service = AdaptiveFilterService(
            memory_service=self.memory_service,
            llm_service=self.llm_service
        )
        await self.adaptive_filter_service.start()
        
        # Initialize agent configuration service
        self.agent_config_service = AgentConfigService(
            memory_service=self.memory_service,
            wa_service=None,  # WA service not yet implemented
            filter_service=self.adaptive_filter_service
        )
        await self.agent_config_service.start()
        
        # Initialize transaction orchestrator
        self.transaction_orchestrator = MultiServiceTransactionOrchestrator(
            service_registry=self.service_registry,
            action_sink=self.multi_service_sink
        )
        await self.transaction_orchestrator.start()
        
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

    async def _register_adapter_services(self) -> None:
        """Register services provided by the loaded adapters."""
        if not self.service_registry:
            logger.error("ServiceRegistry not initialized. Cannot register adapter services.")
            return

        for adapter in self.adapters:
            try:
                registrations = adapter.get_services_to_register()
                for reg in registrations:
                    if not isinstance(reg, ServiceRegistration):
                        logger.error(f"Adapter {adapter.__class__.__name__} provided an invalid ServiceRegistration object: {reg}")
                        continue

                    # Ensure provider is an instance of Service
                    if not isinstance(reg.provider, Service):
                         logger.error(f"Adapter {adapter.__class__.__name__} service provider for {reg.service_type.value} is not a Service instance.")
                         continue

                    if reg.handlers: # Register for specific handlers
                        for handler_name in reg.handlers:
                            self.service_registry.register(
                                handler=handler_name,
                                service_type=reg.service_type.value, # Use the string value of the enum
                                provider=reg.provider,
                                priority=reg.priority,
                                capabilities=reg.capabilities
                            )
                        logger.info(f"Registered {reg.service_type.value} from {adapter.__class__.__name__} for handlers: {reg.handlers}")
                    else: # Register globally if no specific handlers
                        self.service_registry.register_global(
                            service_type=reg.service_type.value,
                            provider=reg.provider,
                            priority=reg.priority,
                            capabilities=reg.capabilities
                        )
                        logger.info(f"Registered {reg.service_type.value} globally from {adapter.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error registering services for adapter {adapter.__class__.__name__}: {e}", exc_info=True)

            
    async def _build_components(self) -> None:
        """Build all processing components."""
        if not self.llm_service:
            raise RuntimeError("LLM service not initialized")
            
        config = self._ensure_config()
        llm_client = self.llm_service.get_client()

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

        dsdma = await create_dsdma_from_profile(
            self.profile,
            self.service_registry,
            model_name=llm_client.model_name,
        )
        
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
        
        graphql_provider = GraphQLContextProvider(
            graphql_client=GraphQLClient() if config.guardrails.enable_remote_graphql else None,
            memory_service=self.memory_service,
            enable_remote_graphql=config.guardrails.enable_remote_graphql
        )
        
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
            app_config=self.app_config,
            telemetry_service=self.telemetry_service
        )
        
        guardrail_orchestrator = GuardrailOrchestrator(guardrail_registry)
        
        await self._register_core_services()
        
        dependencies = ActionHandlerDependencies(
            service_registry=self.service_registry,
            # io_adapter is no longer a direct dependency here, adapters handle IO
            shutdown_callback=lambda: self.request_shutdown(
                "Handler requested shutdown due to critical service failure"
            ),
        )
        dependencies.multi_service_sink = self.multi_service_sink
        dependencies.memory_service = self.memory_service
        dependencies.audit_service = self.audit_service
        
        register_global_shutdown_handler(
            lambda: self.request_shutdown("Global shutdown manager triggered"),
            is_async=False
        )
        
        if not self.app_config:
            raise RuntimeError("AppConfig is required for ThoughtProcessor initialization")
        thought_processor = ThoughtProcessor(
            dma_orchestrator,
            context_builder,
            guardrail_orchestrator,
            self.app_config,
            dependencies,
            telemetry_service=self.telemetry_service
        )
        
        action_dispatcher = await self._build_action_dispatcher(dependencies)
        

        
        if not self.app_config:
            raise RuntimeError("AppConfig is required for AgentProcessor initialization")
        if not self.profile:
            raise RuntimeError("Profile is required for AgentProcessor initialization")
        self.agent_processor = AgentProcessor(
            app_config=self.app_config,
            active_profile=self.profile,
            thought_processor=thought_processor,
            action_dispatcher=action_dispatcher,
            services={
                "llm_service": self.llm_service,
                "memory_service": self.memory_service,
                "audit_service": self.audit_service,
                "service_registry": self.service_registry,
                # "io_adapter": self.io_adapter, # Removed, adapters manage their own IO
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

        # Register telemetry service globally for all handlers and components
        if self.telemetry_service:
            self.service_registry.register_global(
                service_type="telemetry",
                provider=self.telemetry_service,
                priority=Priority.HIGH,
                capabilities=["record_metric", "update_system_snapshot"]
            )
        
        # Register LLM service globally so processors and DMAs can fetch it
        if self.llm_service:
            self.service_registry.register_global(
                service_type="llm",
                provider=self.llm_service,
                priority=Priority.HIGH,
                capabilities=["generate_response", "generate_structured_response"]
            )
        
        # Register secrets service globally for all handlers
        if self.secrets_service:
            self.service_registry.register_global(
                service_type="secrets",
                provider=self.secrets_service,
                priority=Priority.HIGH,
                capabilities=["detect_secrets", "store_secret", "retrieve_secret", "filter_content"]
            )
        
        # Register adaptive filter service
        if self.adaptive_filter_service:
            self.service_registry.register_global(
                service_type="filter",
                provider=self.adaptive_filter_service,
                priority=Priority.HIGH,
                capabilities=["message_filtering", "priority_assessment", "user_trust_tracking"]
            )
        
        # Register agent configuration service
        if self.agent_config_service:
            self.service_registry.register_global(
                service_type="config",
                provider=self.agent_config_service,
                priority=Priority.HIGH,
                capabilities=["self_configuration", "wa_deferral", "config_persistence"]
            )
        
        # Register transaction orchestrator
        if self.transaction_orchestrator:
            self.service_registry.register_global(
                service_type="orchestrator",
                provider=self.transaction_orchestrator,
                priority=Priority.CRITICAL,
                capabilities=["transaction_coordination", "service_routing", "health_monitoring"]
            )
        
        # Note: Communication and WA services will be registered by subclasses
        # (e.g., DiscordRuntime registers Discord adapter, CIRISNode client)
        
    async def _build_action_dispatcher(self, dependencies: Any) -> Any:
        """Build action dispatcher. Override in subclasses for custom sinks."""
        config = self._ensure_config()
        return build_action_dispatcher(
            service_registry=self.service_registry,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=config.workflow.max_rounds,
            telemetry_service=self.telemetry_service,
            multi_service_sink=self.multi_service_sink,
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

            if not self.agent_processor:
                raise RuntimeError("Agent processor not initialized")

            effective_num_rounds = num_rounds if num_rounds is not None else DEFAULT_NUM_ROUNDS
            logger.info(f"Starting agent processing (num_rounds={effective_num_rounds if effective_num_rounds != -1 else 'infinite'})...")

            agent_task = asyncio.create_task(
                self.agent_processor.start_processing(effective_num_rounds),
                name="AgentProcessorTask"
            )
            
            adapter_tasks = [
                asyncio.create_task(adapter.run_lifecycle(agent_task), name=f"{adapter.__class__.__name__}LifecycleTask")
                for adapter in self.adapters
            ]
            
            # Monitor agent_task, all adapter_tasks, and shutdown events
            self._ensure_shutdown_event()
            shutdown_event_task = None
            if self._shutdown_event:
                shutdown_event_task = asyncio.create_task(self._shutdown_event.wait(), name="ShutdownEventWait")
            
            global_shutdown_task = asyncio.create_task(wait_for_global_shutdown(), name="GlobalShutdownWait")
            all_tasks = [agent_task, *adapter_tasks, global_shutdown_task]
            if shutdown_event_task:
                all_tasks.append(shutdown_event_task)
            
            done, pending = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)

            # Handle task completion and cancellation logic
            if (self._shutdown_event and self._shutdown_event.is_set()) or is_global_shutdown_requested():
                shutdown_reason = self._shutdown_reason or self._shutdown_manager.get_shutdown_reason() or "Unknown reason"
                logger.critical(f"GRACEFUL SHUTDOWN TRIGGERED: {shutdown_reason}")
                # Ensure all other tasks are cancelled if a shutdown event occurred
                for task in pending:
                    if not task.done():
                        task.cancel()
                if not agent_task.done(): # Ensure agent task is cancelled if not already
                    agent_task.cancel()
                for ad_task in adapter_tasks: # Ensure adapter tasks are cancelled
                    if not ad_task.done():
                        ad_task.cancel()
            elif agent_task in done:
                logger.info(f"Agent processing task completed. Result: {agent_task.result() if not agent_task.cancelled() else 'Cancelled'}")
                # If agent task finishes (e.g. num_rounds reached), signal shutdown for adapters
                self.request_shutdown("Agent processing completed normally.")
                for ad_task in adapter_tasks: # Adapters should react to agent_task completion via its cancellation or by observing shutdown event
                    if not ad_task.done():
                         ad_task.cancel() # Or rely on their run_lifecycle to exit when agent_task is done
            else: # One of the adapter tasks finished, or an unexpected task completion
                for task in done:
                    if task not in [shutdown_event_task, global_shutdown_task]: # Don't log for event tasks
                        task_name = task.get_name() if hasattr(task, 'get_name') else "Unnamed task"
                        logger.info(f"Task '{task_name}' completed. Result: {task.result() if not task.cancelled() else 'Cancelled'}")
                        if task.exception():
                            logger.error(f"Task '{task_name}' raised an exception: {task.exception()}", exc_info=task.exception())
                            self.request_shutdown(f"Task {task_name} failed: {task.exception()}")

            # Await all pending tasks (including cancellations)
            if pending:
                await asyncio.wait(pending, return_when=asyncio.ALL_COMPLETED)
            
            # Execute any pending global shutdown handlers
            if (self._shutdown_event and self._shutdown_event.is_set()) or is_global_shutdown_requested():
                await self._shutdown_manager.execute_async_handlers()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Requesting shutdown.")
            self.request_shutdown("KeyboardInterrupt")
            # Re-raise to allow outer event loop (if any) to catch it, or ensure finally block runs
            # For this structure, self.request_shutdown and then letting it flow to finally is fine.
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
        finally:
            await self.shutdown()
            
    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        logger.info("Shutting down CIRIS Runtime...")
        
        logger.info("Initiating shutdown sequence for CIRIS Runtime...")
        self._ensure_shutdown_event()
        if self._shutdown_event:
            self._shutdown_event.set() # Ensure event is set for any waiting components

        if self.agent_processor:
            logger.debug("Stopping agent processor...")
            await self.agent_processor.stop_processing()
            logger.debug("Agent processor stopped.")
            
        if self.multi_service_sink:
            logger.debug("Stopping multi-service sink...")
            await self.multi_service_sink.stop()
            logger.debug("Multi-service sink stopped.")

        logger.debug(f"Stopping {len(self.adapters)} adapters...")
        adapter_stop_results = await asyncio.gather(
            *(adapter.stop() for adapter in self.adapters if hasattr(adapter, 'stop')),
            return_exceptions=True
        )
        for i, result in enumerate(adapter_stop_results):
            if isinstance(result, Exception):
                logger.error(f"Error stopping adapter {self.adapters[i].__class__.__name__}: {result}", exc_info=result)
        logger.debug("Adapters stopped.")
            
        logger.debug("Stopping core services...")
        services_to_stop = [
            self.llm_service, # OpenAICompatibleLLM
            self.memory_service,
            self.audit_service,
            self.telemetry_service,
            self.secrets_service,
            self.adaptive_filter_service,
            self.agent_config_service,
            self.transaction_orchestrator,
            self.maintenance_service,
        ]
        
        await asyncio.gather(
            *[s.stop() for s in services_to_stop if s],
            return_exceptions=True
        )
        
        if self.service_registry:
            self.service_registry.clear_all()
            self.service_registry = None
        
        logger.info("CIRIS Runtime shutdown complete")
