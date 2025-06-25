"""
Service initialization for CIRIS Agent runtime.

Handles the initialization of all core services.
"""
import logging
from typing import Any, List, Optional
from pathlib import Path
import os
import json

from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.logic.services.runtime.llm_service import OpenAICompatibleClient
from ciris_engine.protocols.services import LLMService, TelemetryService
from ciris_engine.logic.services.graph.audit_service import GraphAuditService as AuditService
from ciris_engine.logic.services.governance.filter import AdaptiveFilterService
# CoreToolService removed - SELF_HELP moved to memory per user request
# BasicTelemetryCollector removed - using GraphTelemetryService instead
from ciris_engine.logic.services.runtime.secrets_service import SecretsService
from ciris_engine.logic.persistence.maintenance import DatabaseMaintenanceService
from ciris_engine.logic.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.runtime.enums import ServiceType
from ciris_engine.schemas.services.capabilities import LLMCapabilities
from ciris_engine.logic.buses import BusManager
# Removed AuditSinkManager - audit is consolidated, no sink needed
from ciris_engine.logic.services.governance.wise_authority import WiseAuthorityService

# Import new infrastructure services
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.logic.services.lifecycle.shutdown import ShutdownService
from ciris_engine.logic.services.lifecycle.initialization import InitializationService
from ciris_engine.schemas.config.essential import EssentialConfig
from ciris_engine.logic.config.config_accessor import ConfigAccessor
from ciris_engine.schemas.services.nodes import ConfigNode, ConfigValue

logger = logging.getLogger(__name__)

class ServiceInitializer:
    """Manages initialization of all core services."""
    
    def __init__(self, essential_config: Optional[EssentialConfig] = None) -> None:
        self.service_registry: Optional[ServiceRegistry] = None
        self.bus_manager: Optional[Any] = None  # Will be BusManager
        self.essential_config = essential_config or EssentialConfig()
        self.config_accessor: Optional[ConfigAccessor] = None
        
        # Infrastructure services (initialized first)
        self.time_service: Optional[TimeService] = None
        self.shutdown_service: Optional[ShutdownService] = None
        self.initialization_service: Optional[InitializationService] = None
        
        # Create initial config accessor without graph (bootstrap only)
        self.config_accessor = ConfigAccessor(None, self.essential_config)
        
        # Core services
        self.memory_service: Optional[LocalGraphMemoryService] = None
        self.secrets_service: Optional[SecretsService] = None
        self.wa_auth_system: Optional[WiseAuthorityService] = None
        self.telemetry_service: Optional[TelemetryService] = None
        self.llm_service: Optional[LLMService] = None
        self.audit_services: List[Any] = []
        self.audit_service: Optional[AuditService] = None
        # Removed audit_sink_manager - audit is consolidated
        self.adaptive_filter_service: Optional[AdaptiveFilterService] = None
        self.agent_config_service: Optional[Any] = None  # Optional[AgentConfigService]
        self.transaction_orchestrator: Optional[Any] = None  # Optional[MultiServiceTransactionOrchestrator]
        # CoreToolService removed - tools are adapter-only per user request
        self.maintenance_service: Optional[DatabaseMaintenanceService] = None
        self.incident_management_service: Optional[Any] = None  # Will be IncidentManagementService
        self.tsdb_consolidation_service: Optional[Any] = None  # Will be TSDBConsolidationService
        self.resource_monitor_service: Optional[Any] = None  # Will be ResourceMonitorService
        self.config_service: Optional[Any] = None  # Will be GraphConfigService
        
        # Module management
        self.module_loader: Optional[Any] = None  # Will be ModuleLoader
        self.loaded_modules: List[str] = []
        self._skip_llm_init: bool = False  # Set to True if MOCK LLM module detected
    
    async def initialize_infrastructure_services(self) -> None:
        """Initialize infrastructure services that all other services depend on."""
        # Initialize TimeService first - everyone needs time
        self.time_service = TimeService()
        await self.time_service.start()
        logger.info("TimeService initialized")
        
        # Initialize ShutdownService
        self.shutdown_service = ShutdownService()
        await self.shutdown_service.start()
        logger.info("ShutdownService initialized")
        
        # Initialize InitializationService with TimeService
        self.initialization_service = InitializationService(self.time_service)
        await self.initialization_service.start()
        logger.info("InitializationService initialized")
        
        # Initialize ResourceMonitorService
        from ciris_engine.logic.services.infrastructure.resource_monitor import ResourceMonitorService
        from ciris_engine.schemas.services.resources_core import ResourceBudget
        from ciris_engine.logic.persistence import get_sqlite_db_full_path
        
        # Create default resource budget
        budget = ResourceBudget()  # Uses defaults from schema
        self.resource_monitor_service = ResourceMonitorService(
            budget=budget,
            db_path=get_sqlite_db_full_path(),
            time_service=self.time_service
        )
        await self.resource_monitor_service.start()
        logger.info("ResourceMonitorService initialized")
    
    async def initialize_memory_service(self, config: Any) -> None:
        """Initialize the memory service."""
        # Initialize secrets service first (memory service depends on it)
        from ciris_engine.logic.persistence import get_sqlite_db_full_path
        db_path = get_sqlite_db_full_path()
        secrets_db_path = db_path.replace('.db', '_secrets.db')
        self.secrets_service = SecretsService(
            db_path=secrets_db_path,
            time_service=self.time_service
        )
        await self.secrets_service.start()
        logger.info("SecretsService initialized")
        
        # LocalGraphMemoryService uses SQLite by default
        self.memory_service = LocalGraphMemoryService(
            time_service=self.time_service,
            secrets_service=self.secrets_service
        )
        await self.memory_service.start()
        
        logger.info("Memory service initialized")
        
        # Initialize GraphConfigService now that memory service is ready
        from ciris_engine.logic.services.graph.config_service import GraphConfigService
        self.config_service = GraphConfigService(self.memory_service, self.time_service)
        await self.config_service.start()
        logger.info("GraphConfigService initialized")
        
        # Create config accessor with graph service
        self.config_accessor = ConfigAccessor(self.config_service, self.essential_config)
        
        # Migrate essential config to graph
        await self._migrate_config_to_graph()
    
    async def verify_memory_service(self) -> bool:
        """Verify memory service is operational."""
        if not self.memory_service:
            logger.error("Memory service not initialized")
            return False
        
        # Test basic operations
        try:
            from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, GraphNodeAttributes
            # Use a different node type for test - don't pollute CONFIG namespace
            test_node = GraphNode(
                id="_verification_test",
                type=NodeType.AUDIT_ENTRY,  # Use AUDIT_ENTRY for test
                attributes={
                    "created_at": self.time_service.now(),
                    "updated_at": self.time_service.now(),
                    "created_by": "system_verification",
                    "tags": ["test", "verification"],
                    "action": "memory_service_verification",
                    "actor": "system"
                },
                scope=GraphScope.LOCAL
            )
            
            # Test memorize and recall
            await self.memory_service.memorize(test_node)
            
            from ciris_engine.schemas.services.operations import MemoryQuery
            query = MemoryQuery(
                node_id=test_node.id,
                scope=test_node.scope,
                type=test_node.type,
                include_edges=False,
                depth=1
            )
            nodes = await self.memory_service.recall(query)
            
            if not nodes:
                logger.error("Memory service verification failed: no nodes recalled")
                return False
            
            # Clean up
            await self.memory_service.forget(test_node)
            
            logger.info("✓ Memory service verified")
            return True
            
        except Exception as e:
            logger.error(f"Memory service verification error: {e}")
            return False
    
    async def initialize_security_services(self, config: Any, app_config: Any) -> None:
        """Initialize security-related services."""
        # SecretsService already initialized in initialize_memory_service
        
        # Initialize AuthenticationService first
        from ciris_engine.logic.services.infrastructure.authentication import AuthenticationService
        auth_db_path = await self.config_accessor.get_path("database.auth_db", Path("data/ciris_auth.db"))
        self.auth_service = AuthenticationService(
            db_path=str(auth_db_path),
            time_service=self.time_service,
            key_dir=None  # Will use default ~/.ciris/
        )
        await self.auth_service.start()
        logger.info("AuthenticationService initialized")
        
        # Initialize WA authentication system with TimeService and AuthService
        self.wa_auth_system = WiseAuthorityService(
            time_service=self.time_service,
            auth_service=self.auth_service,
            db_path=None  # Will use default from config
        )
        await self.wa_auth_system.start()
        logger.info("WA authentication system initialized")
    
    async def verify_security_services(self) -> bool:
        """Verify security services are operational."""
        # Verify secrets service
        if not self.secrets_service:
            logger.error("Secrets service not initialized")
            return False
        
        # Verify WA auth system
        if not self.wa_auth_system:
            logger.error("WA authentication system not initialized")
            return False
        
        # Verify WA service is healthy
        if not await self.wa_auth_system.is_healthy():
            logger.error("WA auth service not healthy")
            return False
        
        logger.info("✓ Security services verified")
        return True
    
    async def initialize_all_services(self, config: Any, app_config: Any, agent_id: str, startup_channel_id: Optional[str] = None, modules_to_load: Optional[List[str]] = None) -> None:
        """Initialize all remaining core services."""
        self.service_registry = ServiceRegistry()
        
        # Pre-load module loader to check for MOCK modules BEFORE initializing services
        if modules_to_load:
            from ciris_engine.logic.runtime.module_loader import ModuleLoader
            self.module_loader = ModuleLoader()
            
            # Check modules for MOCK status WITHOUT loading them yet
            for module_name in modules_to_load:
                module_path = self.module_loader.modules_dir / module_name
                manifest_path = module_path / "manifest.json"
                
                if manifest_path.exists():
                    try:
                        with open(manifest_path) as f:
                            manifest = json.load(f)
                        
                        module_info = manifest.get("module", {})
                        is_mock = module_info.get("MOCK", False)
                        
                        if is_mock:
                            # This is a MOCK module - check what services it provides
                            services = manifest.get("services", [])
                            for service in services:
                                service_type_str = service.get("type", "")
                                if service_type_str == "LLM":
                                    logger.info(f"Detected MOCK LLM module '{module_name}' will be loaded - skipping normal LLM initialization")
                                    self._skip_llm_init = True
                                    break
                    except Exception as e:
                        logger.warning(f"Failed to pre-check module {module_name}: {e}")
        else:
            modules_to_load = []
        
        # Register previously initialized services in the registry
        # Register previously initialized services in the registry as per CLAUDE.md
        
        # Memory service was initialized in Phase 2, register it now
        if self.memory_service:
            self.service_registry.register_global(
                service_type=ServiceType.MEMORY,
                provider=self.memory_service,
                priority=Priority.HIGH,
                capabilities=["memorize", "recall", "forget", "graph_operations"],
                metadata={"backend": "sqlite", "graph_type": "local"}
            )
            logger.info("Memory service registered in ServiceRegistry")
        
        # WiseAuthority service was initialized in security phase, register it now
        if self.wa_auth_system:
            self.service_registry.register_global(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.wa_auth_system,
                priority=Priority.HIGH,
                capabilities=["authenticate", "authorize", "validate", "guidance"],
                metadata={"type": "consolidated", "consensus": "single"}
            )
            logger.info("WiseAuthority service registered in ServiceRegistry")
        
        # Initialize telemetry service using GraphTelemetryService
        # This implements the "Graph Memory as Identity Architecture" patent
        # where telemetry IS memory stored in the agent's identity graph
        from ciris_engine.logic.services.graph.telemetry_service import GraphTelemetryService
        self.telemetry_service = GraphTelemetryService(
            memory_bus=None,  # Will be set after bus_manager is created
            time_service=self.time_service
        )
        await self.telemetry_service.start()
        logger.info("GraphTelemetryService initialized")
        
        # Create BusManager with service registry and telemetry service
        self.bus_manager = BusManager(
            self.service_registry, 
            self.time_service,
            self.telemetry_service,
            None  # audit_service will be set later
        )
        
        # Now set the memory bus in telemetry service
        self.telemetry_service._memory_bus = self.bus_manager.memory
        
        # Initialize LLM service(s) based on configuration
        await self._initialize_llm_services(config)
        
        # Secrets service no longer needs LLM service reference
        
        # Initialize ALL THREE REQUIRED audit services
        await self._initialize_audit_services(config, agent_id)
        
        # Initialize adaptive filter service
        self.adaptive_filter_service = AdaptiveFilterService(
            memory_service=self.memory_service,
            time_service=self.time_service,
            llm_service=self.llm_service,
            config_service=self.config_service  # Pass GraphConfigService
        )
        await self.adaptive_filter_service.start()
        
        # TODO: Agent configuration service needs to be implemented
        # self.agent_config_service = AgentConfigService(
        #     memory_service=self.memory_service,
        #     wa_service=self.wa_auth_system.get_auth_service() if self.wa_auth_system else None,
        #     filter_service=self.adaptive_filter_service
        # )
        # await self.agent_config_service.start()
        
        # TODO: Transaction orchestrator needs to be implemented
        # self.transaction_orchestrator = MultiServiceTransactionOrchestrator(
        #     service_registry=self.service_registry,
        #     _action_sink=self.bus_manager,
        #     app_config=app_config
        # )
        # await self.transaction_orchestrator.start()
        
        # CoreToolService removed - tools are adapter-only per user request
        # SELF_HELP moved to memory service
        
        # Initialize task scheduler service
        from ciris_engine.logic.services.lifecycle.scheduler import TaskSchedulerService
        self.task_scheduler_service = TaskSchedulerService(
            db_path=getattr(config, "database_path", "data/ciris_engine.db"),
            time_service=self.time_service
        )
        await self.task_scheduler_service.start()
        logger.info("Task scheduler service initialized")
        
        # Initialize maintenance service
        archive_dir = getattr(config, "data_archive_dir", "data_archive")
        archive_hours = getattr(config, "archive_older_than_hours", 24)
        self.maintenance_service = DatabaseMaintenanceService(
            time_service=self.time_service,
            archive_dir_path=archive_dir,
            archive_older_than_hours=archive_hours
        )
        
        # Initialize TSDB consolidation service
        from ciris_engine.logic.services.graph.tsdb_consolidation_service import TSDBConsolidationService
        self.tsdb_consolidation_service = TSDBConsolidationService(
            memory_bus=self.memory_service,  # Direct reference to memory service
            time_service=self.time_service   # Pass time service
        )
        await self.tsdb_consolidation_service.start()
        logger.info("TSDB consolidation service initialized - creating permanent memory summaries every 6 hours")
    
    async def _initialize_llm_services(self, config: Any) -> None:
        """Initialize LLM service(s) based on configuration.
        
        CRITICAL: Only mock OR real LLM services are active, never both.
        This prevents attack vectors where mock responses could be confused with real ones.
        """
        # Check if a MOCK LLM module will be loaded
        if self._skip_llm_init:
            logger.info("🤖 MOCK LLM module detected - skipping normal LLM service initialization")
            logger.info("The MOCK module will provide LLM service when loaded")
            return
        
        # Check if mock LLM is enabled via config (legacy)
        mock_llm_enabled = getattr(config, 'mock_llm', False)
        
        # Also check if we have NO API key - this means mock LLM will be loaded as a module
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key and not mock_llm_enabled:
            logger.info("No API key found and mock_llm not explicitly set - skipping LLM initialization")
            logger.info("Mock LLM will be loaded as a module in the next phase")
            return
        
        if mock_llm_enabled:
            # ONLY register mock LLM service
            logger.info("🤖 Mock LLM mode enabled - registering ONLY mock LLM service")
            
            # Import here to avoid circular imports
            from ciris_modular_services.mock_llm.service import MockLLMService
            
            # Create and start mock service
            mock_service = MockLLMService()
            await mock_service.start()
            
            # Register with CRITICAL priority as the ONLY LLM service
            if self.service_registry:
                self.service_registry.register_global(
                    service_type=ServiceType.LLM,
                    provider=mock_service,
                    priority=Priority.CRITICAL,
                    capabilities=[LLMCapabilities.CALL_LLM_STRUCTURED.value],
                    metadata={"provider": "mock", "warning": "MOCK LLM - NOT FOR PRODUCTION"}
                )
            
            # Store reference for compatibility
            self.llm_service = mock_service
            logger.warning("⚠️  MOCK LLM SERVICE ACTIVE - ALL RESPONSES ARE SIMULATED")
            
        else:
            # ONLY register real LLM service(s)
            logger.info("Initializing real LLM service(s)")
            
            # Check if this is EssentialConfig (bootstrap phase)
            if hasattr(config, 'services'):
                # Using EssentialConfig - create minimal LLM config
                from ciris_engine.logic.services.runtime.llm_service import OpenAIConfig
                llm_config = OpenAIConfig(
                    base_url=config.services.llm_endpoint,
                    model_name=config.services.llm_model,
                    api_key=os.environ.get("OPENAI_API_KEY", ""),
                    timeout_seconds=config.services.llm_timeout,
                    max_retries=config.services.llm_max_retries
                )
            else:
                # Legacy config format (should not happen)
                raise ValueError("Configuration missing LLM service settings")
            
            # Primary OpenAI service
            openai_service = OpenAICompatibleClient(
                llm_config, 
                telemetry_service=self.telemetry_service
            )
            await openai_service.start()
            
            # Register OpenAI as primary
            if self.service_registry:
                self.service_registry.register_global(
                    service_type=ServiceType.LLM,
                    provider=openai_service,
                    priority=Priority.HIGH,
                    capabilities=[LLMCapabilities.CALL_LLM_STRUCTURED.value],
                    metadata={"provider": "openai", "model": llm_config.model_name}
                )
            
            # Store reference for compatibility
            self.llm_service = openai_service
            
            # Future: Add additional real LLM providers here
            # Example for Anthropic (when implemented):
            # anthropic_service = AnthropicLLMService(config.llm_services.anthropic)
            # await anthropic_service.start()
            # self.service_registry.register_global(
            #     service_type=ServiceType.LLM,
            #     provider=anthropic_service,
            #     priority=Priority.NORMAL,
            #     capabilities=["generate_structured_response", "anthropic"],
            #     metadata={"provider": "anthropic"}
            # )
            
            logger.info(f"Real LLM service(s) initialized: {llm_config.model_name}")
    
    async def _initialize_audit_services(self, config: Any, agent_id: str) -> None:
        """Initialize all three required audit services."""
        self.audit_services = []
        
        # Initialize the consolidated GraphAuditService
        logger.info("Initializing consolidated GraphAuditService...")
        
        # The GraphAuditService combines all audit functionality:
        # - Graph-based storage (primary)
        # - Optional file export for compliance
        # - Cryptographic hash chain for integrity
        # - Time-series capabilities built-in
        # Use config accessor for audit configuration
        audit_db_path = await self.config_accessor.get_path("database.audit_db", Path("data/ciris_audit.db"))
        audit_key_path = await self.config_accessor.get_path("security.audit_key_path", Path("audit_keys"))
        retention_days = await self.config_accessor.get_int("security.audit_retention_days", 90)
        
        from ciris_engine.logic.services.graph.audit_service import GraphAuditService
        graph_audit = GraphAuditService(
            memory_bus=None,  # Will be set via service registry
            time_service=self.time_service,
            export_path="audit_logs.jsonl",  # Standard audit log path
            export_format="jsonl",
            enable_hash_chain=True,
            db_path=str(audit_db_path),
            key_path=str(audit_key_path),
            retention_days=retention_days
        )
        await graph_audit.start()
        self.audit_services.append(graph_audit)
        logger.info("Consolidated GraphAuditService started")
        
        # Keep reference to primary audit service for compatibility
        self.audit_service = self.audit_services[0]
        
        # Audit sink manager removed - GraphAuditService handles its own lifecycle
        logger.info("GraphAuditService handles its own retention and cleanup")
        
        # Initialize incident management service (processes audit events as incidents)
        from ciris_engine.logic.services.graph.incident_service import IncidentManagementService
        self.incident_management_service = IncidentManagementService(
            memory_bus=self.bus_manager.memory,
            time_service=self.time_service
        )
        await self.incident_management_service.start()
        logger.info("Incident management service initialized")
    
    async def verify_core_services(self) -> bool:
        """Verify all core services are operational."""
        try:
            # Check service registry
            if not self.service_registry:
                logger.error("Service registry not initialized")
                return False
            
            # Check critical services
            critical_services = [
                self.telemetry_service,
                self.llm_service,
                self.memory_service,
                self.secrets_service,
                self.adaptive_filter_service
            ]
            
            for service in critical_services:
                if not service:
                    logger.error(f"Critical service {type(service).__name__} not initialized")
                    return False
            
            # Verify audit services
            if not self.audit_services or len(self.audit_services) == 0:
                logger.error("No audit services found")
                return False
            
            logger.info("✓ All core services verified")
            return True
        except Exception as e:
            logger.error(f"Core services verification failed: {e}")
            return False
    
    async def load_modules(self, modules: List[str], disable_core_on_mock: bool = True) -> None:
        """Load external modules with MOCK safety checks.
        
        Args:
            modules: List of module names to load (e.g. ["mockllm", "custom_tool"])
            disable_core_on_mock: If True, MOCK modules disable core services
        """
        if not self.module_loader:
            from ciris_engine.logic.runtime.module_loader import ModuleLoader
            self.module_loader = ModuleLoader()
        
        for module_name in modules:
            try:
                # Load module with safety checks
                if self.module_loader.load_module(module_name, disable_core_on_mock):
                    # Initialize services from module
                    services = await self.module_loader.initialize_module_services(
                        module_name, 
                        self.service_registry
                    )
                    
                    self.loaded_modules.append(module_name)
                    logger.info(f"Module {module_name} loaded with {len(services)} services")
                    
                    # Store first LLM service for compatibility
                    for service in services:
                        if hasattr(service, '__class__') and 'LLM' in service.__class__.__name__:
                            self.llm_service = service
                            break
                else:
                    logger.error(f"Failed to load module: {module_name}")
                    
            except Exception as e:
                logger.error(f"Error loading module {module_name}: {e}")
                raise
        
        # Display MOCK warnings if any
        warnings = self.module_loader.get_mock_warnings()
        for warning in warnings:
            logger.warning(warning)
    
    def register_core_services(self) -> None:
        """Register core services in the service registry."""
        if not self.service_registry:
            return
        
        # Infrastructure services are single-instance - NO ServiceRegistry needed
        # Direct references only per "No Kings" principle
        
        # Register memory service globally - ONE instance for ALL handlers
        if self.memory_service:
            self.service_registry.register_global(
                service_type=ServiceType.MEMORY,
                provider=self.memory_service,
                priority=Priority.HIGH,
                capabilities=["memorize", "recall", "forget"],
                metadata={"service_name": "GraphMemoryService", "graph": True}
            )
        
        # Audit service is single-instance - NO ServiceRegistry needed

        # Telemetry service is single-instance - NO ServiceRegistry needed
        
        # Register LLM service(s) - handled by _initialize_llm_services
        
        # Secrets service is single-instance - NO ServiceRegistry needed
        
        # Adaptive filter service is single-instance - NO ServiceRegistry needed
        
        # Register WA service - can have multiple wisdom sources
        if self.wa_auth_system:
            self.service_registry.register_global(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.wa_auth_system,
                priority=Priority.CRITICAL,
                capabilities=[
                    "authenticate", "verify_token", "provision_certificate",
                    "handle_deferral", "provide_guidance", "oauth_flow"
                ],
                metadata={"service_name": "WiseAuthorityService"}
            )
        
        # Config service is single-instance - NO ServiceRegistry needed
        # But it's used by RuntimeControlService so needs to be accessible
        
        # Transaction orchestrator is single-instance - NO ServiceRegistry needed
        
        # CoreToolService removed - tools are adapter-only per user request
        # SELF_HELP moved to memory service
        
        # Task scheduler is single-instance - NO ServiceRegistry needed
        
        # Incident management is single-instance - NO ServiceRegistry needed
    
    async def _migrate_config_to_graph(self) -> None:
        """Migrate essential config to graph for runtime management."""
        if not self.config_service:
            logger.warning("Cannot migrate config - GraphConfigService not available")
            return
            
        logger.info("Migrating essential configuration to graph...")
        
        # Migrate each config section
        config_dict = self.essential_config.model_dump()
        
        for section_name, section_data in config_dict.items():
            if isinstance(section_data, dict):
                # Migrate each key in the section
                for key, value in section_data.items():
                    full_key = f"{section_name}.{key}"
                    await self.config_service.set_config(
                        key=full_key,
                        value=value,  # Pass raw value, set_config will wrap it
                        updated_by="system_bootstrap"
                    )
                    logger.debug(f"Migrated config: {full_key}")
            else:
                # Top-level config value
                await self.config_service.set_config(
                    key=section_name,
                    value=section_data,  # Pass raw value, set_config will wrap it
                    updated_by="system_bootstrap"
                )
                logger.debug(f"Migrated config: {section_name}")
        
        logger.info("Configuration migration complete")