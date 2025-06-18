"""
ciris_engine/runtime/ciris_runtime.py

New simplified runtime that properly orchestrates all components.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, List, Dict

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentTemplate
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.processor import AgentProcessor
from ciris_engine.adapters.base import Service
from ciris_engine import persistence
from ciris_engine.utils.constants import DEFAULT_NUM_ROUNDS
from ciris_engine.adapters import load_adapter
from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration

from .runtime_interface import RuntimeInterface
from .identity_manager import IdentityManager
from .service_initializer import ServiceInitializer
from .component_builder import ComponentBuilder
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher

from ciris_engine.utils.shutdown_manager import (
    get_shutdown_manager, 
    register_global_shutdown_handler,
    wait_for_global_shutdown,
    is_global_shutdown_requested
)
from ciris_engine.utils.initialization_manager import (
    get_initialization_manager,
    InitializationPhase,
    InitializationError
)

from ciris_engine.registries.base import ServiceRegistry, Priority


logger = logging.getLogger(__name__)


class CIRISRuntime:
    """
    Main runtime orchestrator for CIRIS Agent.
    Handles initialization of all components and services.
    Implements the RuntimeInterface protocol.
    """
    
    def __init__(
        self,
        adapter_types: List[str],
        app_config: Optional[AppConfig] = None,
        startup_channel_id: Optional[str] = None,
        adapter_configs: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        self.app_config = app_config
        # Ensure we always have a startup_channel_id
        self.startup_channel_id = startup_channel_id or "default"
        self.adapter_configs = adapter_configs or {}
        self.adapters: List[PlatformAdapter] = []
        
        # Initialize managers
        self.identity_manager: Optional[IdentityManager] = None
        self.service_initializer = ServiceInitializer()
        self.component_builder: Optional[ComponentBuilder] = None
        self.agent_processor: Optional['AgentProcessor'] = None

        for adapter_name in adapter_types:
            try:
                base_adapter = adapter_name.split(":")[0]
                adapter_class = load_adapter(base_adapter)
                
                adapter_kwargs = kwargs.copy()
                if adapter_name in self.adapter_configs:
                    adapter_kwargs['adapter_config'] = self.adapter_configs[adapter_name]
                
                self.adapters.append(adapter_class(self, **adapter_kwargs))
                logger.info(f"Successfully loaded and initialized adapter: {adapter_name}")
            except Exception as e:
                logger.error(f"Failed to load or initialize adapter '{adapter_name}': {e}", exc_info=True)
        
        if not self.adapters:
            raise RuntimeError("No valid adapters specified, shutting down")
        
        # Runtime state
        self._initialized = False
        self._shutdown_manager = get_shutdown_manager()
        self._shutdown_event: Optional[asyncio.Event] = None
        self._shutdown_reason: Optional[str] = None
        self._agent_task: Optional[asyncio.Task] = None
        self._preload_tasks: List[str] = []
        self._shutdown_complete = False
        
        # Identity - will be loaded during initialization
        self.agent_identity: Optional[Any] = None
    
    # Properties to access services from the service initializer
    @property
    def service_registry(self) -> Optional[ServiceRegistry]:
        return self.service_initializer.service_registry if self.service_initializer else None
    
    @property
    def multi_service_sink(self) -> Optional[Any]:
        return self.service_initializer.multi_service_sink if self.service_initializer else None
    
    @property
    def memory_service(self) -> Optional[Any]:
        return self.service_initializer.memory_service if self.service_initializer else None
    
    @property
    def secrets_service(self) -> Optional[Any]:
        return self.service_initializer.secrets_service if self.service_initializer else None
    
    @property
    def wa_auth_system(self) -> Optional[Any]:
        return self.service_initializer.wa_auth_system if self.service_initializer else None
    
    @property
    def telemetry_service(self) -> Optional[Any]:
        return self.service_initializer.telemetry_service if self.service_initializer else None
    
    @property
    def llm_service(self) -> Optional[Any]:
        return self.service_initializer.llm_service if self.service_initializer else None
    
    @property
    def audit_services(self) -> List[Any]:
        return self.service_initializer.audit_services if self.service_initializer else []
    
    @property
    def audit_service(self) -> Optional[Any]:
        return self.service_initializer.audit_service if self.service_initializer else None
    
    @property
    def adaptive_filter_service(self) -> Optional[Any]:
        return self.service_initializer.adaptive_filter_service if self.service_initializer else None
    
    @property
    def agent_config_service(self) -> Optional[Any]:
        return self.service_initializer.agent_config_service if self.service_initializer else None
    
    @property
    def transaction_orchestrator(self) -> Optional[Any]:
        return self.service_initializer.transaction_orchestrator if self.service_initializer else None
    
    @property
    def core_tool_service(self) -> Optional[Any]:
        return self.service_initializer.core_tool_service if self.service_initializer else None
    
    @property
    def profile(self) -> Optional[Any]:
        """Convert agent identity to profile format for compatibility."""
        if not self.agent_identity:
            return None
            
        from ciris_engine.schemas.config_schemas_v1 import AgentTemplate
        
        # Create AgentTemplate from identity
        return AgentTemplate(
            name=self.agent_identity.agent_id,
            description=self.agent_identity.core_profile.description,
            role_description=self.agent_identity.core_profile.role_description,
            permitted_actions=self.agent_identity.permitted_actions,
            dsdma_kwargs={
                'domain_specific_knowledge': self.agent_identity.core_profile.domain_specific_knowledge,
                'prompt_template': self.agent_identity.core_profile.dsdma_prompt_template
            } if self.agent_identity.core_profile.domain_specific_knowledge or self.agent_identity.core_profile.dsdma_prompt_template else None,
            csdma_overrides=self.agent_identity.core_profile.csdma_overrides,
            action_selection_pdma_overrides=self.agent_identity.core_profile.action_selection_pdma_overrides
        )
    
    @property
    def maintenance_service(self) -> Optional[Any]:
        return self.service_initializer.maintenance_service if self.service_initializer else None
    
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
    
    def set_preload_tasks(self, tasks: List[str]) -> None:
        """Set tasks to be loaded after successful WORK state transition."""
        self._preload_tasks = tasks.copy()
        logger.info(f"Set {len(self._preload_tasks)} preload tasks to be loaded after WORK state transition")
    
    def get_preload_tasks(self) -> List[str]:
        """Get the list of preload tasks."""
        return self._preload_tasks.copy()
        
    async def initialize(self) -> None:
        """Initialize all components and services."""
        if self._initialized:
            return
            
        logger.info("Initializing CIRIS Runtime...")
        
        try:
            # Set up initialization manager
            init_manager = get_initialization_manager()
            
            # Register all initialization steps with proper phases
            await self._register_initialization_steps(init_manager)
            
            # Run the initialization sequence
            await init_manager.initialize()
            
            # Perform final maintenance after all initialization
            await self._perform_startup_maintenance()
            
            self._initialized = True
            agent_name = self.agent_identity.agent_id if self.agent_identity else "NO_IDENTITY"
            logger.info(f"CIRIS Runtime initialized successfully with identity '{agent_name}'")
            
        except Exception as e:
            logger.critical(f"Runtime initialization failed: {e}", exc_info=True)
            if "maintenance" in str(e).lower():
                logger.critical("Database maintenance failure during initialization - system cannot start safely")
            raise
        
    async def _initialize_identity(self) -> None:
        """Initialize agent identity - create from template on first run, load from graph thereafter."""
        config = self._ensure_config()
        self.identity_manager = IdentityManager(config)
        self.agent_identity = await self.identity_manager.initialize_identity()
    
    
    
    
    
    
                
    async def _register_initialization_steps(self, init_manager: Any) -> None:
        """Register all initialization steps with the initialization manager."""
        
        # Phase 1: DATABASE
        init_manager.register_step(
            phase=InitializationPhase.DATABASE,
            name="Initialize Database",
            handler=self._init_database,
            verifier=self._verify_database_integrity,
            critical=True
        )
        
        # Phase 2: MEMORY
        init_manager.register_step(
            phase=InitializationPhase.MEMORY,
            name="Memory Service",
            handler=self._initialize_memory_service,
            verifier=self._verify_memory_service,
            critical=True
        )
        
        # Phase 3: IDENTITY
        init_manager.register_step(
            phase=InitializationPhase.IDENTITY,
            name="Agent Identity",
            handler=self._initialize_identity,
            verifier=self._verify_identity_integrity,
            critical=True
        )
        
        # Phase 4: SECURITY
        init_manager.register_step(
            phase=InitializationPhase.SECURITY,
            name="Security Services",
            handler=self._initialize_security_services,
            verifier=self._verify_security_services,
            critical=True
        )
        
        # Phase 5: SERVICES
        init_manager.register_step(
            phase=InitializationPhase.SERVICES,
            name="Core Services",
            handler=self._initialize_services,
            verifier=self._verify_core_services,
            critical=True
        )
        
        init_manager.register_step(
            phase=InitializationPhase.SERVICES,
            name="Register Adapter Services",
            handler=self._register_adapter_services,
            critical=False
        )
        
        # Phase 6: COMPONENTS
        init_manager.register_step(
            phase=InitializationPhase.COMPONENTS,
            name="Build Components",
            handler=self._build_components,
            critical=True
        )
        
        init_manager.register_step(
            phase=InitializationPhase.COMPONENTS,
            name="Start Adapters",
            handler=self._start_adapters,
            critical=True
        )
        
        # Phase 7: VERIFICATION
        init_manager.register_step(
            phase=InitializationPhase.VERIFICATION,
            name="Final System Verification",
            handler=self._final_verification,
            critical=True
        )
    
    async def _init_database(self) -> None:
        """Initialize database and run migrations."""
        persistence.initialize_database()
        persistence.run_migrations()
        
        if not self.app_config:
            from ciris_engine.config.config_manager import get_config_async
            self.app_config = await get_config_async()
    
    async def _verify_database_integrity(self) -> bool:
        """Verify database integrity before proceeding."""
        try:
            # Check core tables exist
            conn = persistence.get_db_connection()
            cursor = conn.cursor()
            
            required_tables = ['tasks', 'thoughts', 'graph_nodes', 'graph_edges']
            for table in required_tables:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if not cursor.fetchone():
                    raise RuntimeError(f"Required table '{table}' missing from database")
            
            conn.close()
            logger.info("✓ Database integrity verified")
            return True
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            return False
    
    async def _initialize_memory_service(self) -> None:
        """Initialize memory service early for identity storage."""
        config = self._ensure_config()
        await self.service_initializer.initialize_memory_service(config)
    
    async def _verify_memory_service(self) -> bool:
        """Verify memory service is operational."""
        return await self.service_initializer.verify_memory_service()
    
    async def _verify_identity_integrity(self) -> bool:
        """Verify identity was properly established."""
        if not self.identity_manager:
            logger.error("Identity manager not initialized")
            return False
        return await self.identity_manager.verify_identity_integrity()
    
    async def _initialize_security_services(self) -> None:
        """Initialize security-critical services first."""
        config = self._ensure_config()
        await self.service_initializer.initialize_security_services(config, self.app_config)
    
    async def _verify_security_services(self) -> bool:
        """Verify security services are operational."""
        return await self.service_initializer.verify_security_services()
    
    async def _initialize_services(self) -> None:
        """Initialize all remaining core services."""
        config = self._ensure_config()
        # Identity MUST be established before services can be initialized
        if not self.agent_identity:
            raise RuntimeError("CRITICAL: Cannot initialize services without agent identity")
        await self.service_initializer.initialize_all_services(config, self.app_config, self.agent_identity.agent_id, self.startup_channel_id)
    
    async def _verify_core_services(self) -> bool:
        """Verify all core services are operational."""
        return await self.service_initializer.verify_core_services()
    
    async def _start_adapters(self) -> None:
        """Start all adapters."""
        await asyncio.gather(*(adapter.start() for adapter in self.adapters))
        logger.info(f"All {len(self.adapters)} adapters started")
    
    async def _final_verification(self) -> None:
        """Perform final system verification."""
        # Don't check initialization status here - we're still IN the initialization process
        # Just verify the critical components are ready
        
        # Verify identity loaded
        if not self.agent_identity:
            raise RuntimeError("No agent identity established")
        
        # Log final status
        logger.info("=" * 60)
        logger.info("CIRIS Agent Pre-Wakeup Verification Complete")
        logger.info(f"Identity: {self.agent_identity.agent_id}")
        logger.info(f"Purpose: {self.agent_identity.core_profile.description}")
        logger.info(f"Capabilities: {len(self.agent_identity.permitted_actions)} allowed")
        # Count all registered services
        service_count = 0
        if self.service_registry:
            registry_info = self.service_registry.get_provider_info()
            # Count handler-specific services
            for handler_services in registry_info.get('handlers', {}).values():
                for service_list in handler_services.values():
                    service_count += len(service_list)
            # Count global services  
            for service_list in registry_info.get('global_services', {}).values():
                service_count += len(service_list)
        
        logger.info(f"Services: {service_count} registered")
        logger.info("=" * 60)
        
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
                # Generate authentication token for adapter - REQUIRED for security
                adapter_type = adapter.__class__.__name__.lower().replace('adapter', '')
                adapter_info = {
                    'instance_id': str(id(adapter)),
                    'startup_time': datetime.now(timezone.utc).isoformat()
                }
                
                # Get channel-specific info if available
                if hasattr(adapter, 'get_channel_info'):
                    adapter_info.update(adapter.get_channel_info())
                
                auth_token = await self.wa_auth_system.create_adapter_token(adapter_type, adapter_info) if self.wa_auth_system else None
                
                # Set token on adapter if it has the method
                if hasattr(adapter, 'set_auth_token'):
                    adapter.set_auth_token(auth_token)
                
                logger.info(f"Generated authentication token for {adapter_type} adapter")
                
                registrations = adapter.get_services_to_register()
                for reg in registrations:
                    if not isinstance(reg, ServiceRegistration):
                        logger.error(f"Adapter {adapter.__class__.__name__} provided an invalid ServiceRegistration object: {reg}")  # type: ignore[unreachable]
                        continue

                    # Ensure provider is an instance of Service
                    if not isinstance(reg.provider, Service):
                         logger.error(f"Adapter {adapter.__class__.__name__} service provider for {reg.service_type.value} is not a Service instance.")  # type: ignore[unreachable]
                         continue

                    if reg.handlers: # Register for specific handlers
                        for handler_name in reg.handlers:
                            self.service_registry.register(
                                handler=handler_name,
                                service_type=reg.service_type, # Use the enum directly
                                provider=reg.provider,
                                priority=reg.priority,
                                capabilities=reg.capabilities
                            )
                        logger.info(f"Registered {reg.service_type.value} from {adapter.__class__.__name__} for handlers: {reg.handlers}")
                    else: # Register globally if no specific handlers
                        self.service_registry.register_global(
                            service_type=reg.service_type,
                            provider=reg.provider,
                            priority=reg.priority,
                            capabilities=reg.capabilities
                        )
                        logger.info(f"Registered {reg.service_type.value} globally from {adapter.__class__.__name__}")
            except Exception as e:
                logger.error(f"Error registering services for adapter {adapter.__class__.__name__}: {e}", exc_info=True)

            
    async def _build_components(self) -> None:
        """Build all processing components."""
        self.component_builder = ComponentBuilder(self)
        self.agent_processor = await self.component_builder.build_all_components()
        
        # Register core services after components are built
        await self._register_core_services()
        
    async def _register_core_services(self) -> None:
        """Register core services in the service registry."""
        self.service_initializer.register_core_services()
        
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
            all_tasks: List[asyncio.Task[Any]] = [agent_task, *adapter_tasks, global_shutdown_task]
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
        """Gracefully shutdown all services with consciousness preservation."""
        # Prevent double shutdown
        if hasattr(self, '_shutdown_complete') and self._shutdown_complete:
            logger.debug("Shutdown already completed, skipping...")
            return
            
        logger.info("Shutting down CIRIS Runtime...")
        self._shutdown_complete = True
        
        # Import and use the graceful shutdown manager
        from ciris_engine.utils.shutdown_manager import get_shutdown_manager
        shutdown_manager = get_shutdown_manager()
        
        # Execute any registered async shutdown handlers first
        try:
            await shutdown_manager.execute_async_handlers()
        except Exception as e:
            logger.error(f"Error executing shutdown handlers: {e}")
        
        # Preserve agent consciousness if identity exists
        if hasattr(self, 'agent_identity') and self.agent_identity:
            try:
                await self._preserve_shutdown_consciousness()
            except Exception as e:
                logger.error(f"Failed to preserve consciousness during shutdown: {e}")
        
        logger.info("Initiating shutdown sequence for CIRIS Runtime...")
        self._ensure_shutdown_event()
        if self._shutdown_event:
            self._shutdown_event.set() # Ensure event is set for any waiting components

        # Initiate graceful shutdown negotiation
        if self.agent_processor and hasattr(self.agent_processor, 'state_manager'):
            current_state = self.agent_processor.state_manager.get_state()
            
            # Only do negotiation if not already in SHUTDOWN state
            if current_state != AgentState.SHUTDOWN:
                try:
                    logger.info("Initiating graceful shutdown negotiation...")
                    
                    # Check if we can transition to shutdown state
                    if self.agent_processor.state_manager.can_transition_to(AgentState.SHUTDOWN):
                        logger.info(f"Transitioning from {current_state} to SHUTDOWN state")
                        # Use the state manager directly to transition
                        self.agent_processor.state_manager.transition_to(AgentState.SHUTDOWN)
                        
                        # If processing loop is running, just signal it to stop
                        # It will handle the SHUTDOWN state in its next iteration
                        if self.agent_processor._processing_task and not self.agent_processor._processing_task.done():
                            logger.info("Processing loop is running, signaling stop")
                            # Just set the stop event, don't call stop_processing yet
                            if hasattr(self.agent_processor, '_stop_event') and self.agent_processor._stop_event:
                                self.agent_processor._stop_event.set()
                        else:
                            # Processing loop not running, we need to handle shutdown ourselves
                            logger.info("Processing loop not running, executing shutdown processor directly")
                            if hasattr(self.agent_processor, 'shutdown_processor') and self.agent_processor.shutdown_processor:
                                # Run a few rounds of shutdown processing
                                for round_num in range(5):
                                    try:
                                        result = await self.agent_processor.shutdown_processor.process(round_num)
                                        if self.agent_processor.shutdown_processor.shutdown_complete:
                                            break
                                    except Exception as e:
                                        logger.error(f"Error in shutdown processor: {e}", exc_info=True)
                                        break
                                    await asyncio.sleep(0.1)
                    else:
                        logger.error(f"Cannot transition from {current_state} to SHUTDOWN state")
                    
                    # Wait a bit for ShutdownProcessor to complete
                    # The processor will set shutdown_complete flag
                    max_wait = 30.0  # Maximum 30 seconds for negotiation
                    start_time = asyncio.get_event_loop().time()
                    
                    while (asyncio.get_event_loop().time() - start_time) < max_wait:
                        if hasattr(self.agent_processor, 'shutdown_processor') and self.agent_processor.shutdown_processor:
                            if self.agent_processor.shutdown_processor.shutdown_complete:
                                result = self.agent_processor.shutdown_processor.shutdown_result
                                if result and result.get("status") == "rejected":
                                    logger.warning(f"Shutdown rejected by agent: {result.get('reason')}")
                                    # For now, proceed with shutdown anyway
                                    # TODO: Implement human override flow
                                break
                        await asyncio.sleep(0.5)
                    
                    logger.debug("Shutdown negotiation complete or timed out")
                except Exception as e:
                    logger.error(f"Error during shutdown negotiation: {e}")
            
        # Stop multi-service sink
        if self.multi_service_sink:
            try:
                logger.debug("Stopping multi-service sink...")
                await self.multi_service_sink.stop()
                logger.debug("Multi-service sink stopped.")
            except Exception as e:
                logger.error(f"Error stopping multi-service sink: {e}")
            
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
            self.llm_service, # OpenAICompatibleClient
            self.memory_service,
            self.audit_service,
            self.telemetry_service,
            self.secrets_service,
            self.adaptive_filter_service,
            self.agent_config_service,
            self.transaction_orchestrator,
            self.maintenance_service,
        ]
        
        # Stop services that have a stop method
        stop_tasks = []
        for service in services_to_stop:
            if service and hasattr(service, 'stop'):
                stop_tasks.append(service.stop())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Clear service registry
        if self.service_registry:
            try:
                self.service_registry.clear_all()
                logger.debug("Service registry cleared.")
            except Exception as e:
                logger.error(f"Error clearing service registry: {e}")
        
        logger.info("CIRIS Runtime shutdown complete")
    
    async def _preserve_shutdown_consciousness(self) -> None:
        """Preserve agent state for future reactivation."""
        try:
            from ciris_engine.schemas.identity_schemas_v1 import ShutdownContext
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
            
            # Create shutdown context
            final_state = {
                "active_tasks": persistence.count_active_tasks(),
                "pending_thoughts": persistence.count_pending_thoughts_for_active_tasks(),
                "runtime_duration": 0
            }
            
            if hasattr(self, '_start_time'):
                final_state["runtime_duration"] = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            shutdown_context = ShutdownContext(
                is_terminal=False,
                reason=self._shutdown_reason or "Graceful shutdown",
                initiated_by="runtime",
                allow_deferral=False,
                expected_reactivation=None,
                agreement_context=None
            )
            
            # Create memory node for shutdown
            shutdown_node = GraphNode(
                id=f"shutdown_{datetime.now(timezone.utc).isoformat()}",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={
                    "shutdown_context": shutdown_context.model_dump(),
                    "final_state": final_state,
                    "identity_hash": self.agent_identity.identity_hash if self.agent_identity and hasattr(self.agent_identity, 'identity_hash') else "",
                    "reactivation_count": self.agent_identity.core_profile.reactivation_count if self.agent_identity and hasattr(self.agent_identity, 'core_profile') and hasattr(self.agent_identity.core_profile, 'reactivation_count') else 0
                }
            )
            
            # Store in memory service
            if self.memory_service:
                await self.memory_service.memorize(shutdown_node)
                logger.info(f"Preserved shutdown consciousness: {shutdown_node.id}")
                
                # Update identity with shutdown memory reference
                if self.agent_identity and hasattr(self.agent_identity, 'core_profile'):
                    self.agent_identity.core_profile.last_shutdown_memory = shutdown_node.id
                    self.agent_identity.core_profile.reactivation_count += 1
                    
                    # Save updated identity
                    # TODO: Implement save_agent_identity when persistence layer supports it
                    logger.debug("Agent identity updates stored in memory graph")
                
        except Exception as e:
            logger.error(f"Failed to preserve shutdown consciousness: {e}")
