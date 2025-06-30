"""
ciris_engine/runtime/ciris_runtime.py

New simplified runtime that properly orchestrates all components.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Any

from ciris_engine.schemas.config.essential import EssentialConfig
from ciris_engine.schemas.processors.states import AgentState
from ciris_engine.logic.processors import AgentProcessor
from ciris_engine.logic import persistence
from ciris_engine.logic.utils.constants import DEFAULT_NUM_ROUNDS
from ciris_engine.logic.adapters import load_adapter
from ciris_engine.protocols.runtime.base import BaseAdapterProtocol
from ciris_engine.schemas.adapters import AdapterServiceRegistration

from .identity_manager import IdentityManager
from .service_initializer import ServiceInitializer
from .component_builder import ComponentBuilder
from ciris_engine.logic.infrastructure.handlers.handler_registry import build_action_dispatcher

from ciris_engine.logic.utils.shutdown_manager import (
    get_shutdown_manager,
    wait_for_global_shutdown_async,
    is_global_shutdown_requested
)
from ciris_engine.logic.utils.initialization_manager import get_initialization_manager
from ciris_engine.schemas.services.operations import InitializationPhase

from ciris_engine.logic.registries.base import ServiceRegistry

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

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
        essential_config: Optional[EssentialConfig] = None,
        startup_channel_id: Optional[str] = None,
        adapter_configs: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        self.essential_config = essential_config
        # Ensure we always have a startup_channel_id
        self.startup_channel_id = startup_channel_id or "default"
        self.adapter_configs = adapter_configs or {}
        self.adapters: List[BaseAdapterProtocol] = []
        self.modules_to_load = kwargs.get('modules', [])

        # Initialize managers
        self.identity_manager: Optional[IdentityManager] = None
        self.service_initializer = ServiceInitializer(essential_config=essential_config)
        self.service_initializer._modules_to_load = self.modules_to_load  # Pass modules to service initializer
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
    def bus_manager(self) -> Optional[Any]:
        return self.service_initializer.bus_manager if self.service_initializer else None

    @property
    def memory_service(self) -> Optional[Any]:
        return self.service_initializer.memory_service if self.service_initializer else None

    @property
    def resource_monitor(self) -> Optional[Any]:
        """Access to resource monitor service - CRITICAL for mission-critical systems."""
        return self.service_initializer.resource_monitor_service if self.service_initializer else None

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
    def config_manager(self) -> Optional[Any]:
        """Return GraphConfigService for RuntimeControlService compatibility."""
        return self.service_initializer.config_service if self.service_initializer else None

    @property
    def transaction_orchestrator(self) -> Optional[Any]:
        return self.service_initializer.transaction_orchestrator if self.service_initializer else None

    @property
    def core_tool_service(self) -> Optional[Any]:
        return self.service_initializer.core_tool_service if self.service_initializer else None

    @property
    def time_service(self) -> Optional[TimeServiceProtocol]:
        return self.service_initializer.time_service if self.service_initializer else None

    @property
    def config_service(self) -> Optional[Any]:
        """Access to configuration service."""
        return self.service_initializer.config_service if self.service_initializer else None

    @property
    def task_scheduler(self) -> Optional[Any]:
        """Access to task scheduler service."""
        return self.service_initializer.task_scheduler_service if self.service_initializer else None

    @property
    def authentication_service(self) -> Optional[Any]:
        """Access to authentication service."""
        return self.service_initializer.auth_service if self.service_initializer else None

    @property
    def incident_management_service(self) -> Optional[Any]:
        """Access to incident management service."""
        return self.service_initializer.incident_management_service if self.service_initializer else None

    @property
    def profile(self) -> Optional[Any]:
        """Convert agent identity to profile format for compatibility."""
        if not self.agent_identity:
            return None

        from ciris_engine.schemas.config.agent import AgentTemplate

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
    
    @property
    def shutdown_service(self) -> Optional[Any]:
        """Access to shutdown service."""
        return self.service_initializer.shutdown_service if self.service_initializer else None
    
    @property
    def initialization_service(self) -> Optional[Any]:
        """Access to initialization service."""
        return self.service_initializer.initialization_service if self.service_initializer else None
    
    @property
    def tsdb_consolidation_service(self) -> Optional[Any]:
        """Access to TSDB consolidation service."""
        return self.service_initializer.tsdb_consolidation_service if self.service_initializer else None
    
    @property
    def secrets_service(self) -> Optional[Any]:
        """Access to secrets service."""
        return self.service_initializer.secrets_service if self.service_initializer else None
    
    @property
    def adaptive_filter_service(self) -> Optional[Any]:
        """Access to adaptive filter service."""
        return self.service_initializer.adaptive_filter_service if self.service_initializer else None
    
    @property
    def self_observation_service(self) -> Optional[Any]:
        """Access to self observation service."""
        return self.service_initializer.self_observation_service if self.service_initializer else None
    
    @property
    def visibility_service(self) -> Optional[Any]:
        """Access to visibility service."""
        return self.service_initializer.visibility_service if self.service_initializer else None

    def _ensure_shutdown_event(self) -> None:
        """Ensure shutdown event is created when needed in async context."""
        if self._shutdown_event is None:
            try:
                self._shutdown_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create shutdown event outside of async context")

    def _ensure_config(self) -> EssentialConfig:
        """Ensure essential_config is available, raise if not."""
        if not self.essential_config:
            raise RuntimeError("Essential config not initialized")
        return self.essential_config

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

        # Use the sync version from shutdown_manager utils to avoid async/await issues
        from ciris_engine.logic.utils.shutdown_manager import request_global_shutdown
        request_global_shutdown(f"Runtime: {reason}")

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

            # Run startup maintenance to clean up invalid data from previous runs
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
        if not self.time_service:
            raise RuntimeError("TimeService not available for IdentityManager")
        self.identity_manager = IdentityManager(config, self.time_service)
        self.agent_identity = await self.identity_manager.initialize_identity()







    async def _register_initialization_steps(self, init_manager: Any) -> None:
        """Register all initialization steps with the initialization manager."""

        # Phase 0: INFRASTRUCTURE (NEW - must be first)
        init_manager.register_step(
            phase=InitializationPhase.INFRASTRUCTURE,
            name="Initialize Infrastructure Services",
            handler=self._initialize_infrastructure,
            verifier=self._verify_infrastructure,
            critical=True
        )

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

        # Start adapters BEFORE registering their services
        init_manager.register_step(
            phase=InitializationPhase.SERVICES,
            name="Start Adapters",
            handler=self._start_adapters,
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
            name="Initialize Maintenance Service",
            handler=self._initialize_maintenance_service,
            critical=True
        )

        # Phase 7: VERIFICATION
        init_manager.register_step(
            phase=InitializationPhase.VERIFICATION,
            name="Final System Verification",
            handler=self._final_verification,
            critical=True
        )

    async def _initialize_infrastructure(self) -> None:
        """Initialize infrastructure services that all other services depend on."""
        await self.service_initializer.initialize_infrastructure_services()

        # Now setup proper file logging with TimeService
        from ciris_engine.logic.utils.logging_config import setup_basic_logging
        if self.service_initializer.time_service:
            # Check if we're in CLI interactive mode
            is_cli_interactive = False
            for adapter in self.adapters:
                adapter_class_name = adapter.__class__.__name__
                if adapter_class_name == "CliPlatform" and hasattr(adapter, 'cli_adapter') and hasattr(adapter.cli_adapter, 'interactive'):
                    is_cli_interactive = adapter.cli_adapter.interactive
                    break

            # Disable console output for CLI interactive mode to avoid cluttering the interface
            console_output = not is_cli_interactive

            logger.info("Setting up file logging with TimeService")
            setup_basic_logging(
                level=logging.DEBUG if logger.isEnabledFor(logging.DEBUG) else logging.INFO,
                log_to_file=True,
                console_output=console_output,
                time_service=self.service_initializer.time_service
            )

    async def _verify_infrastructure(self) -> bool:
        """Verify infrastructure services are operational."""
        # Check that all infrastructure services are running
        if not self.service_initializer.time_service:
            logger.error("TimeService not initialized")
            return False
        if not self.service_initializer.shutdown_service:
            logger.error("ShutdownService not initialized")
            return False
        if not self.service_initializer.initialization_service:
            logger.error("InitializationService not initialized")
            return False
        return True

    async def _init_database(self) -> None:
        """Initialize database and run migrations."""
        # Pass the db path from our config
        db_path = persistence.get_sqlite_db_full_path()
        persistence.initialize_database(db_path)
        persistence.run_migrations()

        if not self.essential_config:
            # Use default essential config if none provided
            self.essential_config = EssentialConfig()
            logger.warning("No config provided, using defaults")

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
        await self.service_initializer.initialize_security_services(config, self.essential_config)

    async def _verify_security_services(self) -> bool:
        """Verify security services are operational."""
        return await self.service_initializer.verify_security_services()

    async def _initialize_services(self) -> None:
        """Initialize all remaining core services."""
        config = self._ensure_config()
        # Identity MUST be established before services can be initialized
        if not self.agent_identity:
            raise RuntimeError("CRITICAL: Cannot initialize services without agent identity")
        await self.service_initializer.initialize_all_services(config, self.essential_config, self.agent_identity.agent_id, self.startup_channel_id, self.modules_to_load)

        # Load any external modules (e.g. mockllm)
        if self.modules_to_load:
            logger.info(f"Loading {len(self.modules_to_load)} external modules: {self.modules_to_load}")
            await self.service_initializer.load_modules(self.modules_to_load)

    async def _verify_core_services(self) -> bool:
        """Verify all core services are operational."""
        return await self.service_initializer.verify_core_services()

    async def _initialize_maintenance_service(self) -> None:
        """Initialize the maintenance service and perform startup cleanup."""
        # Verify maintenance service is available
        if not self.maintenance_service:
            raise RuntimeError("Maintenance service was not initialized properly")
        logger.info("Maintenance service verified available")

        # Perform startup maintenance to clean stale tasks
        await self._perform_startup_maintenance()

    async def _start_adapters(self) -> None:
        """Start all adapters."""
        await asyncio.gather(*(adapter.start() for adapter in self.adapters))
        logger.info(f"All {len(self.adapters)} adapters started")

        # Give adapters time to establish connections (especially Discord)
        await asyncio.sleep(5.0)
        logger.info("Adapter startup grace period complete")

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
                    'startup_time': self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
                }

                # Get channel-specific info if available
                if hasattr(adapter, 'get_channel_info'):
                    adapter_info.update(adapter.get_channel_info())

                # Get authentication service from service initializer
                auth_service = self.service_initializer.auth_service if self.service_initializer else None

                # Create adapter token using the proper authentication service
                auth_token = await auth_service._create_channel_token_for_adapter(adapter_type, adapter_info) if auth_service else None

                # Set token on adapter if it has the method
                if hasattr(adapter, 'set_auth_token') and auth_token:
                    adapter.set_auth_token(auth_token)

                if auth_token:
                    logger.info(f"Generated authentication token for {adapter_type} adapter")

                registrations = adapter.get_services_to_register()
                for reg in registrations:
                    if not isinstance(reg, AdapterServiceRegistration):
                        logger.error(f"Adapter {adapter.__class__.__name__} provided an invalid AdapterServiceRegistration object: {reg}")
                        continue

                    # No need to check Service base class - adapters implement protocol interfaces

                    # All services are global now
                    self.service_registry.register_service(
                        service_type=reg.service_type, # Use the enum directly
                        provider=reg.provider,
                        priority=reg.priority,
                        capabilities=reg.capabilities
                    )
                    logger.info(f"Registered {reg.service_type.value} from {adapter.__class__.__name__}")
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

    async def _build_action_dispatcher(self, dependencies: Any):
        """Build action dispatcher. Override in subclasses for custom sinks."""
        config = self._ensure_config()
        # Create BusManager for action handlers
        from ciris_engine.logic.buses import BusManager
        if not self.service_registry:
            raise RuntimeError("Service registry not initialized")
        bus_manager = BusManager(self.service_registry)

        return build_action_dispatcher(
            bus_manager=bus_manager,
            time_service=self.time_service,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=config.workflow.max_rounds,
            telemetry_service=self.telemetry_service,
            secrets_service=self.secrets_service,
        )

    async def run(self, num_rounds: Optional[int] = None) -> None:
        """Run the agent processing loop with shutdown monitoring."""
        if not self._initialized:
            await self.initialize()

        try:
            # Start multi-service sink processing as background task
            if self.bus_manager:
                _sink_task = asyncio.create_task(self.bus_manager.start())
                logger.info("Started multi-service sink as background task")

            if not self.agent_processor:
                raise RuntimeError("Agent processor not initialized")

            # Wait for at least one communication service to be available
            logger.info("Waiting for communication service to be available...")
            max_wait = 30.0  # Wait up to 30 seconds for adapters to connect
            start_time = asyncio.get_event_loop().time()

            while (asyncio.get_event_loop().time() - start_time) < max_wait:
                # Check if any communication service is available
                from ciris_engine.schemas.runtime.enums import ServiceType
                comm_service = await self.service_registry.get_service(
                    handler="SpeakHandler",
                    service_type=ServiceType.COMMUNICATION,
                    required_capabilities=["send_message"]
                )
                if comm_service:
                    logger.info("Communication service available, starting agent processor")
                    break
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"No communication service available after {max_wait} seconds, starting anyway")

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

            global_shutdown_task = asyncio.create_task(wait_for_global_shutdown_async(), name="GlobalShutdownWait")
            all_tasks: List[asyncio.Task[Any]] = [agent_task, *adapter_tasks, global_shutdown_task]
            if shutdown_event_task:
                all_tasks.append(shutdown_event_task)

            # Keep monitoring until agent task completes
            shutdown_logged = False
            while not agent_task.done():
                done, pending = await asyncio.wait(all_tasks, return_when=asyncio.FIRST_COMPLETED)

                # Remove completed tasks from all_tasks to avoid re-processing
                all_tasks = [t for t in all_tasks if t not in done]

                # Handle task completion and cancellation logic
                if (self._shutdown_event and self._shutdown_event.is_set()) or is_global_shutdown_requested():
                    if not shutdown_logged:
                        shutdown_reason = self._shutdown_reason or self._shutdown_manager.get_shutdown_reason() or "Unknown reason"
                        logger.critical(f"GRACEFUL SHUTDOWN TRIGGERED: {shutdown_reason}")
                        shutdown_logged = True
                    # Don't cancel anything! Let the graceful shutdown process handle it
                    # The agent processor will transition to SHUTDOWN state and handle everything
                    # Continue the loop - wait for agent to finish its shutdown process
                elif agent_task in done:
                    logger.info(f"Agent processing task completed. Result: {agent_task.result() if not agent_task.cancelled() else 'Cancelled'}")
                    # If agent task finishes (e.g. num_rounds reached), signal shutdown for adapters
                    self.request_shutdown("Agent processing completed normally.")
                    for ad_task in adapter_tasks: # Adapters should react to agent_task completion via its cancellation or by observing shutdown event
                        if not ad_task.done():
                             ad_task.cancel() # Or rely on their run_lifecycle to exit when agent_task is done
                    break  # Exit the while loop
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
            logger.debug("Runtime.run() entering finally block")
            await self.shutdown()
            logger.debug("Runtime.run() exiting finally block")

    async def shutdown(self) -> None:
        """Gracefully shutdown all services with consciousness preservation."""
        # Prevent double shutdown
        if hasattr(self, '_shutdown_complete') and self._shutdown_complete:
            logger.debug("Shutdown already completed, skipping...")
            return

        logger.info("Shutting down CIRIS Runtime...")

        # Import and use the graceful shutdown manager
        from ciris_engine.logic.utils.shutdown_manager import get_shutdown_manager
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
                    max_wait = 5.0  # Reduced from 30s to 5s for faster shutdown
                    start_time = asyncio.get_event_loop().time()

                    while (asyncio.get_event_loop().time() - start_time) < max_wait:
                        if hasattr(self.agent_processor, 'shutdown_processor') and self.agent_processor.shutdown_processor:
                            if self.agent_processor.shutdown_processor.shutdown_complete:
                                result = self.agent_processor.shutdown_processor.shutdown_result or {}
                                if result and result.get("status") == "rejected":
                                    logger.warning(f"Shutdown rejected by agent: {result.get('reason')}")
                                    # For now, proceed with shutdown anyway
                                    # TODO: Implement human override flow
                                break
                        await asyncio.sleep(0.1)  # Reduced from 0.5s to 0.1s for faster response

                    logger.debug("Shutdown negotiation complete or timed out")
                except Exception as e:
                    logger.error(f"Error during shutdown negotiation: {e}")

        # Stop multi-service sink
        if self.bus_manager:
            try:
                logger.debug("Stopping multi-service sink...")
                await self.bus_manager.stop()
                logger.debug("Multi-service sink stopped.")
            except Exception as e:
                logger.error(f"Error stopping multi-service sink: {e}")

        logger.debug(f"Stopping {len(self.adapters)} adapters...")
        adapter_stop_results = await asyncio.gather(
            *(adapter.stop() for adapter in self.adapters if hasattr(adapter, 'stop')),
            return_exceptions=True
        )
        for i, stop_result in enumerate(adapter_stop_results):
            if isinstance(stop_result, Exception):
                logger.error(f"Error stopping adapter {self.adapters[i].__class__.__name__}: {stop_result}", exc_info=stop_result)
        logger.debug("Adapters stopped.")

        logger.debug("Stopping core services...")
        # Stop services in reverse dependency order
        # Services that depend on others should be stopped first
        services_to_stop = []

        # First stop services that depend on memory/telemetry
        if hasattr(self.service_initializer, 'tsdb_consolidation_service') and self.service_initializer.tsdb_consolidation_service:
            services_to_stop.append(self.service_initializer.tsdb_consolidation_service)
        if hasattr(self.service_initializer, 'task_scheduler_service') and self.service_initializer.task_scheduler_service:
            services_to_stop.append(self.service_initializer.task_scheduler_service)
        if hasattr(self.service_initializer, 'incident_management_service') and self.service_initializer.incident_management_service:
            services_to_stop.append(self.service_initializer.incident_management_service)
        if hasattr(self.service_initializer, 'resource_monitor_service') and self.service_initializer.resource_monitor_service:
            services_to_stop.append(self.service_initializer.resource_monitor_service)
        if hasattr(self.service_initializer, 'config_service') and self.service_initializer.config_service:
            services_to_stop.append(self.service_initializer.config_service)

        # Then stop higher-level services
        if self.maintenance_service:
            services_to_stop.append(self.maintenance_service)
        if self.transaction_orchestrator:
            services_to_stop.append(self.transaction_orchestrator)
        if self.agent_config_service:
            services_to_stop.append(self.agent_config_service)
        if self.adaptive_filter_service:
            services_to_stop.append(self.adaptive_filter_service)

        # Stop services that use memory service
        if self.telemetry_service:
            services_to_stop.append(self.telemetry_service)  # Depends on memory service
        if self.audit_service:
            services_to_stop.append(self.audit_service)      # May depend on memory service

        # Stop other core services
        if self.llm_service:
            services_to_stop.append(self.llm_service)        # OpenAICompatibleClient
        if hasattr(self.service_initializer, 'wa_auth_system') and self.service_initializer.wa_auth_system:
            services_to_stop.append(self.service_initializer.wa_auth_system)

        # Stop fundamental services last
        if self.secrets_service:
            services_to_stop.append(self.secrets_service)
        if self.memory_service:
            services_to_stop.append(self.memory_service)     # Core dependency, stop last

        # Finally stop infrastructure services
        if hasattr(self.service_initializer, 'initialization_service') and self.service_initializer.initialization_service:
            services_to_stop.append(self.service_initializer.initialization_service)
        if hasattr(self.service_initializer, 'shutdown_service') and self.service_initializer.shutdown_service:
            services_to_stop.append(self.service_initializer.shutdown_service)
        if hasattr(self.service_initializer, 'time_service') and self.service_initializer.time_service:
            services_to_stop.append(self.service_initializer.time_service)

        # Stop services that have a stop method
        stop_tasks = []
        service_names = []
        for service in services_to_stop:
            if service and hasattr(service, 'stop'):
                # Create tasks so we can check their status
                task = asyncio.create_task(service.stop())
                stop_tasks.append(task)
                service_names.append(service.__class__.__name__)

        if stop_tasks:
            logger.info(f"Stopping {len(stop_tasks)} services: {', '.join(service_names)}")
            
            # Use wait with timeout instead of wait_for to better track individual tasks
            done, pending = await asyncio.wait(stop_tasks, timeout=10.0)
            
            if pending:
                # Some tasks didn't complete
                logger.error(f"Service shutdown timed out after 10 seconds. {len(pending)} services still running.")
                hanging_services = []
                
                for task in pending:
                    # Find which service this task belongs to
                    try:
                        idx = stop_tasks.index(task)
                        service_name = service_names[idx]
                        hanging_services.append(service_name)
                        logger.warning(f"Service {service_name} did not stop in time")
                    except ValueError:
                        logger.warning("Unknown service task did not stop in time")
                    
                    # Cancel the hanging task
                    task.cancel()
                
                logger.error(f"Hanging services: {', '.join(hanging_services)}")
                
                # Try to await cancelled tasks to clean up properly
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
            else:
                logger.info(f"All {len(stop_tasks)} services stopped successfully")
            
            # Check for any errors in completed tasks
            for task in done:
                if task.done() and not task.cancelled():
                    try:
                        result = task.result()
                        if isinstance(result, Exception):
                            idx = stop_tasks.index(task)
                            logger.error(f"Service {service_names[idx]} stop error: {result}")
                    except Exception as e:
                        logger.error(f"Error checking task result: {e}")

        # Clear service registry
        if self.service_registry:
            try:
                self.service_registry.clear_all()
                logger.debug("Service registry cleared.")
            except Exception as e:
                logger.error(f"Error clearing service registry: {e}")

        logger.info("CIRIS Runtime shutdown complete")
        
        # Mark shutdown as truly complete
        self._shutdown_complete = True
        logger.debug("Shutdown method returning")

    async def _preserve_shutdown_consciousness(self) -> None:
        """Preserve agent state for future reactivation."""
        try:
            from ciris_engine.schemas.runtime.extended import ShutdownContext
            from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType

            # Create shutdown context
            final_state = {
                "active_tasks": persistence.count_active_tasks(),
                "pending_thoughts": persistence.count_pending_thoughts_for_active_tasks(),
                "runtime_duration": 0
            }

            if hasattr(self, '_start_time'):
                final_state["runtime_duration"] = (self.time_service.now() - self._start_time).total_seconds() if self.time_service else 0

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
                id=f"shutdown_{self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()}",
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

                    # Increment reactivation count in metadata if it exists
                    if hasattr(self.agent_identity, 'identity_metadata'):
                        self.agent_identity.identity_metadata.modification_count += 1

                    # Save updated identity
                    # TODO: Implement save_agent_identity when persistence layer supports it
                    logger.debug("Agent identity updates stored in memory graph")

        except Exception as e:
            logger.error(f"Failed to preserve shutdown consciousness: {e}")
