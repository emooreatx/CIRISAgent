"""
Service initialization for CIRIS Agent runtime.

Handles the initialization of all core services.
"""
import logging
from typing import Optional, List, Any
from datetime import datetime, timezone

from ciris_engine.services.memory_service import LocalGraphMemoryService
from ciris_engine.services.llm_service import OpenAICompatibleClient
from ciris_engine.services.audit_service import AuditService
from ciris_engine.services.signed_audit_service import SignedAuditService
from ciris_engine.services.tsdb_audit_service import TSDBSignedAuditService
from ciris_engine.services.adaptive_filter_service import AdaptiveFilterService
from ciris_engine.services.agent_config_service import AgentConfigService
from ciris_engine.services.multi_service_transaction_orchestrator import MultiServiceTransactionOrchestrator
from ciris_engine.services.core_tool_service import CoreToolService
from ciris_engine.telemetry import TelemetryService, SecurityFilter
from ciris_engine.secrets.service import SecretsService
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.runtime.audit_sink_manager import AuditSinkManager
from ciris_engine.services.wa_auth_integration import initialize_authentication, WAAuthenticationSystem

logger = logging.getLogger(__name__)


class ServiceInitializer:
    """Manages initialization of all core services."""
    
    def __init__(self) -> None:
        self.service_registry: Optional[ServiceRegistry] = None
        self.multi_service_sink: Optional[MultiServiceActionSink] = None
        self.memory_service: Optional[LocalGraphMemoryService] = None
        self.secrets_service: Optional[SecretsService] = None
        self.wa_auth_system: Optional[WAAuthenticationSystem] = None
        self.telemetry_service: Optional[TelemetryService] = None
        self.llm_service: Optional[OpenAICompatibleClient] = None
        self.audit_services: List[Any] = []
        self.audit_service: Optional[AuditService] = None
        self.audit_sink_manager: Optional[AuditSinkManager] = None
        self.adaptive_filter_service: Optional[AdaptiveFilterService] = None
        self.agent_config_service: Optional[AgentConfigService] = None
        self.transaction_orchestrator: Optional[MultiServiceTransactionOrchestrator] = None
        self.core_tool_service: Optional[CoreToolService] = None
        self.maintenance_service: Optional[DatabaseMaintenanceService] = None
    
    async def initialize_memory_service(self, config: Any) -> None:
        """Initialize the memory service."""
        # Use database config for memory service
        import os
        memory_db_path = os.path.join(config.database.data_directory, config.database.graph_memory_filename)
        self.memory_service = LocalGraphMemoryService(db_path=memory_db_path)
        await self.memory_service.start()
        logger.info("Memory service initialized")
    
    async def verify_memory_service(self) -> bool:
        """Verify memory service is operational."""
        if not self.memory_service:
            logger.error("Memory service not initialized")
            return False
        
        # Test basic operations
        try:
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
            test_node = GraphNode(
                id="_verification_test",
                type=NodeType.CONFIG,
                attributes={"test": True, "timestamp": datetime.now(timezone.utc).isoformat()},
                scope=GraphScope.LOCAL
            )
            
            # Test memorize and recall
            await self.memory_service.memorize(test_node)
            result = await self.memory_service.recall(test_node)
            
            if result.status.value != "ok":
                logger.error(f"Memory service verification failed: status={result.status.value}")
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
        # Initialize secrets service
        self.secrets_service = SecretsService(
            db_path=config.secrets.storage.database_path,  # Use the correct path from storage config
            master_key=None  # Will use default key generation
        )
        await self.secrets_service.start()
        logger.info("Secrets service initialized")
        
        # Initialize WA authentication system
        self.wa_auth_system = await initialize_authentication(
            db_path=None,  # Will use default from config
            key_dir=None   # Will use default ~/.ciris/
        )
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
        
        # Verify gateway secret exists
        auth_service = self.wa_auth_system.get_auth_service()
        if not auth_service:
            logger.error("WA auth service not available")
            return False
        
        logger.info("✓ Security services verified")
        return True
    
    async def initialize_all_services(self, config: Any, app_config: Any, agent_id: str, startup_channel_id: Optional[str] = None) -> None:
        """Initialize all remaining core services."""
        self.service_registry = ServiceRegistry()
        
        self.multi_service_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            max_queue_size=1000,
            fallback_channel_id=startup_channel_id,
        )
        
        # Initialize telemetry service first so other services can use it
        self.telemetry_service = TelemetryService(
            buffer_size=1000,
            security_filter=SecurityFilter()
        )
        await self.telemetry_service.start()
        
        # Initialize LLM service(s) based on configuration
        await self._initialize_llm_services(config)
        
        # Secrets service no longer needs LLM service reference
        
        # Initialize ALL THREE REQUIRED audit services
        await self._initialize_audit_services(config, agent_id)
        
        # Initialize adaptive filter service
        self.adaptive_filter_service = AdaptiveFilterService(
            memory_service=self.memory_service,
            llm_service=self.llm_service
        )
        await self.adaptive_filter_service.start()
        
        # Initialize agent configuration service
        self.agent_config_service = AgentConfigService(
            memory_service=self.memory_service,
            wa_service=self.wa_auth_system.get_auth_service() if self.wa_auth_system else None,
            filter_service=self.adaptive_filter_service
        )
        await self.agent_config_service.start()
        
        # Initialize transaction orchestrator
        self.transaction_orchestrator = MultiServiceTransactionOrchestrator(
            service_registry=self.service_registry,
            action_sink=self.multi_service_sink,
            app_config=app_config
        )
        await self.transaction_orchestrator.start()
        
        # Initialize core tool service
        self.core_tool_service = CoreToolService()
        await self.core_tool_service.start()
        logger.info("Core tool service initialized with system-wide tools")
        
        # Initialize maintenance service
        archive_dir = getattr(config, "data_archive_dir", "data_archive")
        archive_hours = getattr(config, "archive_older_than_hours", 24)
        self.maintenance_service = DatabaseMaintenanceService(
            archive_dir_path=archive_dir,
            archive_older_than_hours=archive_hours
        )
    
    async def _initialize_llm_services(self, config: Any) -> None:
        """Initialize LLM service(s) based on configuration.
        
        CRITICAL: Only mock OR real LLM services are active, never both.
        This prevents attack vectors where mock responses could be confused with real ones.
        """
        # Check if mock LLM is enabled
        mock_llm_enabled = getattr(config, 'mock_llm', False)
        
        if mock_llm_enabled:
            # ONLY register mock LLM service
            logger.info("🤖 Mock LLM mode enabled - registering ONLY mock LLM service")
            
            # Import here to avoid circular imports
            from ciris_engine.services.mock_llm import MockLLMService
            
            # Create and start mock service
            mock_service = MockLLMService()
            await mock_service.start()
            
            # Register with CRITICAL priority as the ONLY LLM service
            self.service_registry.register_global(
                service_type=ServiceType.LLM,
                provider=mock_service,
                priority=Priority.CRITICAL,
                capabilities=["generate_structured_response", "mock_llm"],
                metadata={"provider": "mock", "warning": "MOCK LLM - NOT FOR PRODUCTION"}
            )
            
            # Store reference for compatibility
            self.llm_service = mock_service
            logger.warning("⚠️  MOCK LLM SERVICE ACTIVE - ALL RESPONSES ARE SIMULATED")
            
        else:
            # ONLY register real LLM service(s)
            logger.info("Initializing real LLM service(s)")
            
            # Primary OpenAI service
            openai_service = OpenAICompatibleClient(
                config.llm_services.openai, 
                telemetry_service=self.telemetry_service
            )
            await openai_service.start()
            
            # Register OpenAI as primary
            self.service_registry.register_global(
                service_type=ServiceType.LLM,
                provider=openai_service,
                priority=Priority.HIGH,
                capabilities=["generate_structured_response", "openai"],
                metadata={"provider": "openai", "model": config.llm_services.openai.model_name}
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
            
            logger.info(f"Real LLM service(s) initialized: {config.llm_services.openai.model_name}")
    
    async def _initialize_audit_services(self, config: Any, agent_id: str) -> None:
        """Initialize all three required audit services."""
        self.audit_services = []
        
        # 1. Basic file-based audit service (REQUIRED - legacy compatibility and fast writes)
        logger.info("Initializing basic file-based audit service...")
        basic_audit = AuditService(
            log_path=config.audit.audit_log_path,
            rotation_size_mb=config.audit.rotation_size_mb,
            retention_days=config.audit.retention_days
        )
        await basic_audit.start()
        self.audit_services.append(basic_audit)
        logger.info("Basic audit service started")
        
        # 2. Signed audit service (REQUIRED - cryptographic integrity)
        logger.info("Initializing cryptographically signed audit service...")
        signed_audit = SignedAuditService(
            log_path=f"{config.audit.audit_log_path}.signed",  # Separate file to avoid conflicts
            db_path=config.audit.audit_db_path,
            key_path=config.audit.audit_key_path,
            rotation_size_mb=config.audit.rotation_size_mb,
            retention_days=config.audit.retention_days,
            enable_jsonl=False,  # Don't double-write to JSONL
            enable_signed=True
        )
        await signed_audit.start()
        self.audit_services.append(signed_audit)
        logger.info("Signed audit service started")
        
        # 3. TSDB audit service (REQUIRED - time-series queries and correlations)
        logger.info("Initializing TSDB audit service...")
        tsdb_audit = TSDBSignedAuditService(
            tags={"agent_id": agent_id},
            retention_policy="raw",
            enable_file_backup=False,  # We already have file backup from service #1
            file_audit_service=None
        )
        await tsdb_audit.start()
        # TSDB audit service is a valid audit service type
        self.audit_services.append(tsdb_audit)
        logger.info("TSDB audit service started")
        
        # Verify all 3 services are running
        if len(self.audit_services) != 3:
            raise RuntimeError(f"FATAL: Expected 3 audit services, got {len(self.audit_services)}. System cannot continue.")
        
        logger.info("All 3 required audit services initialized successfully")
        
        # Keep reference to primary audit service for compatibility
        self.audit_service = self.audit_services[0]
        
        # Initialize audit sink manager to handle lifecycle and cleanup
        self.audit_sink_manager = AuditSinkManager(
            retention_seconds=300,  # 5 minutes
            min_consumers=3,  # All 3 audit services must acknowledge
            cleanup_interval_seconds=60
        )
        
        # Register all audit services as consumers
        for i, audit_service in enumerate(self.audit_services):
            consumer_id = f"{audit_service.__class__.__name__}_{i}"
            self.audit_sink_manager.register_consumer(consumer_id)
            
        await self.audit_sink_manager.start()
        logger.info("Audit sink manager started with 3 registered consumers")
    
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
                self.adaptive_filter_service,
                self.core_tool_service
            ]
            
            for service in critical_services:
                if not service:
                    logger.error(f"Critical service {type(service).__name__} not initialized")
                    return False
            
            # Verify audit services
            if not self.audit_services or len(self.audit_services) != 3:
                logger.error(f"Expected 3 audit services, found {len(self.audit_services) if self.audit_services else 0}")
                return False
            
            logger.info("✓ All core services verified")
            return True
        except Exception as e:
            logger.error(f"Core services verification failed: {e}")
            return False
    
    def register_core_services(self) -> None:
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
                    service_type=ServiceType.MEMORY,
                    provider=self.memory_service,
                    priority=Priority.HIGH,
                    capabilities=["memorize", "recall", "forget"]
                )
        
        # Register ALL audit services globally - the sink will route to all of them
        if hasattr(self, 'audit_services') and self.audit_services:
            for i, audit_service in enumerate(self.audit_services):
                # Determine capabilities based on service type
                capabilities = ["log_action", "log_event"]
                service_name = audit_service.__class__.__name__
                
                if "Signed" in service_name:
                    capabilities.extend(["verify_integrity", "rotate_keys", "create_root_anchor"])
                if "TSDB" in service_name:
                    capabilities.extend(["time_series_query", "correlation_tracking"])
                else:
                    capabilities.append("get_audit_trail")
                
                # Register with different priorities so sink can route appropriately
                priority = Priority.CRITICAL if i == 0 else Priority.HIGH
                
                self.service_registry.register_global(
                    service_type=ServiceType.AUDIT,
                    provider=audit_service,
                    priority=priority,
                    capabilities=capabilities,
                    metadata={"audit_type": service_name}
                )

        # Register telemetry service globally for all handlers and components
        if self.telemetry_service:
            self.service_registry.register_global(
                service_type=ServiceType.TELEMETRY,
                provider=self.telemetry_service,
                priority=Priority.HIGH,
                capabilities=["record_metric", "update_system_snapshot"]
            )
        
        # Register LLM service(s) - handled by _initialize_llm_services
        
        # Register secrets service globally for all handlers
        if self.secrets_service:
            self.service_registry.register_global(
                service_type=ServiceType.SECRETS,
                provider=self.secrets_service,
                priority=Priority.HIGH,
                capabilities=["detect_secrets", "store_secret", "retrieve_secret", "filter_content"]
            )
        
        # Register adaptive filter service
        if self.adaptive_filter_service:
            self.service_registry.register_global(
                service_type=ServiceType.FILTER,
                provider=self.adaptive_filter_service,
                priority=Priority.HIGH,
                capabilities=["message_filtering", "priority_assessment", "user_trust_tracking"]
            )
        
        # Register agent configuration service
        if self.agent_config_service:
            self.service_registry.register_global(
                service_type=ServiceType.CONFIG,
                provider=self.agent_config_service,
                priority=Priority.HIGH,
                capabilities=["self_configuration", "wa_deferral", "config_persistence"]
            )
        
        # Register transaction orchestrator
        if self.transaction_orchestrator:
            self.service_registry.register_global(
                service_type=ServiceType.ORCHESTRATOR,
                provider=self.transaction_orchestrator,
                priority=Priority.CRITICAL,
                capabilities=["transaction_coordination", "service_routing", "health_monitoring", "audit_broadcast"]
            )
        
        # Register core tool service globally so it's available to all handlers
        if hasattr(self, 'core_tool_service') and self.core_tool_service:
            self.service_registry.register_global(
                service_type=ServiceType.TOOL,
                provider=self.core_tool_service,
                priority=Priority.HIGH,
                capabilities=["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"],
                metadata={"service_name": "CoreToolService", "provides_system_tools": True}
            )
            logger.info("Registered CoreToolService globally with SELF_HELP and other system tools")