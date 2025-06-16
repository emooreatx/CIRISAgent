"""
ciris_engine/runtime/ciris_runtime.py

New simplified runtime that properly orchestrates all components.
"""
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, List, Dict

from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.processor import AgentProcessor
from ciris_engine.adapters.base import Service
from ciris_engine import persistence
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.utils.constants import DEFAULT_NUM_ROUNDS
from ciris_engine.adapters import load_adapter
from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration

from ciris_engine.services.memory_service import LocalGraphMemoryService
from ciris_engine.services.llm_service import OpenAICompatibleClient
from ciris_engine.services.audit_service import AuditService
from ciris_engine.services.signed_audit_service import SignedAuditService
from ciris_engine.services.tsdb_audit_service import TSDBSignedAuditService
from ciris_engine.persistence.maintenance import DatabaseMaintenanceService
from .runtime_interface import RuntimeInterface
from .audit_sink_manager import AuditSinkManager
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
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
from ciris_engine.services.wa_auth_integration import initialize_authentication, WAAuthenticationSystem


logger = logging.getLogger(__name__)


class CIRISRuntime(RuntimeInterface):
    """
    Main runtime orchestrator for CIRIS Agent.
    Handles initialization of all components and services.
    """
    
    def __init__(
        self,
        adapter_types: List[str],
        profile_name: str = "default",
        app_config: Optional[AppConfig] = None,
        startup_channel_id: Optional[str] = None,
        adapter_configs: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        self.profile_name = profile_name
        self.app_config = app_config
        self.startup_channel_id = startup_channel_id
        self.adapter_configs = adapter_configs or {}
        self.adapters: List[PlatformAdapter] = []

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
        
        self.llm_service: Optional[OpenAICompatibleClient] = None
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
        
        self._preload_tasks: List[str] = []
        
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
            
        logger.info(f"Initializing CIRIS Runtime with profile '{self.profile_name}'...")
        
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
            logger.info("CIRIS Runtime initialized successfully")
            
        except Exception as e:
            logger.critical(f"Runtime initialization failed: {e}", exc_info=True)
            if "maintenance" in str(e).lower():
                logger.critical("Database maintenance failure during initialization - system cannot start safely")
            raise
        
    async def _initialize_identity(self) -> None:
        """Initialize agent identity - create from profile on first run, load from graph thereafter."""
        config = self._ensure_config()
        
        # Check if identity exists in graph
        identity_data = await self._get_identity_from_graph()
        
        if identity_data:
            # Identity exists - load it and use it
            logger.info("Loading existing agent identity from graph")
            from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot
            self.agent_identity = AgentIdentityRoot.model_validate(identity_data)
            
            # Create a minimal profile object for compatibility
            # This will be removed once all systems use identity directly
            self.profile = self._create_profile_from_identity(self.agent_identity)
        else:
            # First run - use profile to create initial identity
            logger.info("No identity found, creating from profile (first run only)")
            
            # Load profile ONLY for initial identity creation
            profile_path = Path(config.profile_directory) / f"{self.profile_name}.yaml"
            initial_profile = await load_profile(profile_path)
            
            if not initial_profile:
                logger.warning(f"Profile '{self.profile_name}' not found, using default")
                default_path = Path(config.profile_directory) / "default.yaml"
                initial_profile = await load_profile(default_path)
                
            if not initial_profile:
                raise RuntimeError("No profile available for initial identity creation")
            
            # Create identity from profile and save to graph
            self.agent_identity = await self._create_identity_from_profile(initial_profile)
            await self._save_identity_to_graph(self.agent_identity)
            
            # Keep profile for compatibility during transition
            self.profile = initial_profile
        
        # Store in config for backward compatibility (to be removed)
        config.agent_profiles[self.agent_identity.agent_id.lower()] = self.profile
    
    async def _get_identity_from_graph(self) -> Optional[Dict[str, Any]]:
        """Retrieve agent identity from the graph memory."""
        if not self.memory_service:
            return None
            
        try:
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
            
            identity_node = GraphNode(
                id="agent/identity",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY
            )
            result = await self.memory_service.recall(identity_node)
            
            if result and result.nodes:
                return result.nodes[0].attributes.get("identity")
        except Exception as e:
            logger.warning(f"Failed to retrieve identity from graph: {e}")
        
        return None
    
    async def _save_identity_to_graph(self, identity: Any) -> None:
        """Save agent identity to the graph memory."""
        if not self.memory_service:
            logger.error("Cannot save identity - memory service not available")
            return
            
        try:
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
            
            identity_node = GraphNode(
                id="agent/identity",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={
                    "identity": identity.model_dump(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "version": "1.0"
                }
            )
            await self.memory_service.memorize(identity_node)
            logger.info("Agent identity saved to graph")
        except Exception as e:
            logger.error(f"Failed to save identity to graph: {e}")
            raise
    
    def _create_profile_from_identity(self, identity: Any) -> AgentProfile:
        """Create a minimal profile object from identity for backward compatibility."""
        # Create a profile that matches the identity settings
        return AgentProfile(
            name=identity.agent_id,
            description=identity.core_profile.description,
            role_description=identity.core_profile.role_description,
            dsdma_identifier=getattr(identity.core_profile, 'dsdma_identifier', 'moderation'),
            # Initialize overrides from identity if available
            dsdma_overrides=getattr(identity.core_profile, 'dsdma_overrides', {}),
            csdma_overrides=getattr(identity.core_profile, 'csdma_overrides', {}),
            action_selection_pdma_overrides=getattr(identity.core_profile, 'action_selection_pdma_overrides', {})
        )
    
    async def _create_identity_from_profile(self, profile: AgentProfile) -> Any:
        """Create initial identity from profile (first run only)."""
        from ciris_engine.schemas.identity_schemas_v1 import (
            AgentIdentityRoot, 
            CoreProfile,
            IdentityMetadata
        )
        import hashlib
        
        # Generate deterministic identity hash
        identity_string = f"{profile.name}:{profile.description}:{profile.role_description}"
        identity_hash = hashlib.sha256(identity_string.encode()).hexdigest()
        
        # Create identity root from profile
        return AgentIdentityRoot(
            agent_id=profile.name,
            identity_hash=identity_hash,
            core_profile=CoreProfile(
                description=profile.description,
                role_description=profile.role_description,
                dsdma_identifier=profile.dsdma_identifier,
                dsdma_overrides=profile.dsdma_overrides or {},
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
    
    def _calculate_profile_variance(self, identity_profile: Any, current_profile: Any) -> float:
        """Calculate variance between identity profile and current profile."""
        # Compare key attributes
        variance_points = 0
        total_points = 0
        
        # Name change is significant
        if identity_profile.name != current_profile.name:
            variance_points += 3
        total_points += 3
        
        # Description change
        if identity_profile.description != current_profile.description:
            variance_points += 2
        total_points += 2
        
        # Role description change
        if identity_profile.role_description != current_profile.role_description:
            variance_points += 2
        total_points += 2
        
        # DSDMA identifier change is critical
        if identity_profile.dsdma_identifier != current_profile.dsdma_identifier:
            variance_points += 5
        total_points += 5
        
        # Check overrides
        for override_type in ['dsdma_overrides', 'csdma_overrides', 'action_selection_pdma_overrides']:
            identity_overrides = getattr(identity_profile, override_type, {})
            current_overrides = getattr(current_profile, override_type, {})
            
            # Count changed keys
            all_keys = set(identity_overrides.keys()) | set(current_overrides.keys())
            changed_keys = 0
            
            for key in all_keys:
                if identity_overrides.get(key) != current_overrides.get(key):
                    changed_keys += 1
            
            if all_keys:
                variance_points += (changed_keys / len(all_keys)) * 2
            total_points += 2
        
        return variance_points / total_points if total_points > 0 else 0
    
    def _create_profile_from_identity(self, identity: Any) -> Any:
        """Create a minimal profile object from identity for backward compatibility."""
        # This is a temporary shim until all systems use identity directly
        from types import SimpleNamespace
        
        profile = SimpleNamespace()
        profile.name = identity.agent_id
        profile.description = identity.core_profile.description
        profile.role_description = identity.core_profile.role_description
        profile.dsdma_identifier = identity.core_profile.dsdma_identifier
        profile.dsdma_overrides = identity.core_profile.dsdma_overrides
        profile.csdma_overrides = identity.core_profile.csdma_overrides
        profile.action_selection_pdma_overrides = identity.core_profile.action_selection_pdma_overrides
        profile.reactivation_count = identity.core_profile.reactivation_count
        
        return profile
    
    async def _create_identity_from_profile(self, initial_profile: Any) -> Any:
        """Create initial agent identity from profile."""
        from ciris_engine.schemas.identity_schemas_v1 import (
            AgentIdentityRoot, CreationCeremony, AgentProfile
        )
        import uuid
        
        # Create ceremony record
        ceremony = CreationCeremony(
            ceremony_id=str(uuid.uuid4()),
            human_id="bootstrap",
            human_name="System Bootstrap",
            agent_id=initial_profile.name,
            agent_name=initial_profile.name,
            purpose_statement=initial_profile.description,
            success=True,
            identity_hash="pending",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Create identity
        identity = AgentIdentityRoot(
            agent_id=initial_profile.name,
            creation_ceremony_id=ceremony.ceremony_id,
            identity_hash=self._compute_identity_hash(initial_profile),
            core_profile=initial_profile,
            wa_approver_id="bootstrap",
            created_human_id="bootstrap",
            created_agent_id=None,
            profile_variance_threshold=0.20,
            allowed_capabilities=self._get_default_capabilities(),
            restricted_capabilities=self._get_restricted_capabilities(initial_profile),
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        return identity
    
    def _compute_identity_hash(self, profile: Any) -> str:
        """Compute hash of core profile attributes."""
        import hashlib
        import json
        
        core_data = {
            "name": profile.name,
            "description": profile.description,
            "role_description": profile.role_description,
            "dsdma_identifier": profile.dsdma_identifier
        }
        
        data_str = json.dumps(core_data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()
    
    def _get_default_capabilities(self) -> List[str]:
        """Get default allowed capabilities."""
        return [
            "observe", "speak", "ponder", "defer", "memorize", "recall",
            "task_complete", "tool_use_safe"
        ]
    
    def _get_restricted_capabilities(self, profile: Any) -> List[str]:
        """Get restricted capabilities based on profile."""
        restricted = []
        
        # Restrict dangerous tools for certain profiles
        if profile.name in ["student", "child", "restricted"]:
            restricted.extend(["tool_use_admin", "reject_with_filter"])
        
        return restricted
                
    async def _register_initialization_steps(self, init_manager) -> None:
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
        try:
            self.memory_service = LocalGraphMemoryService()
            await self.memory_service.start()
            logger.info("✓ Memory service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize memory service: {e}")
            raise RuntimeError(f"Cannot proceed without memory service: {e}")
    
    async def _verify_memory_service(self) -> bool:
        """Verify memory service is operational."""
        try:
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
            
            # Test write and read
            test_node = GraphNode(
                id="test/startup_verification",
                type=NodeType.AGENT,
                scope=GraphScope.LOCAL,
                attributes={"test": True, "timestamp": datetime.now(timezone.utc).isoformat()}
            )
            
            await self.memory_service.memorize(test_node)
            result = await self.memory_service.recall(test_node)
            
            if not result or not result.nodes:
                raise RuntimeError("Memory service verification failed - cannot read test data")
            
            # Clean up test data
            await self.memory_service.forget(test_node)
            logger.info("✓ Memory service verified")
            return True
        except Exception as e:
            logger.error(f"Memory service verification failed: {e}")
            return False
    
    async def _verify_identity_integrity(self) -> bool:
        """Verify identity was properly established."""
        if not self.agent_identity:
            logger.error("Identity initialization failed - no identity established")
            return False
        
        # Verify critical identity fields
        required_fields = ['agent_id', 'identity_hash', 'core_profile', 'allowed_capabilities']
        for field in required_fields:
            if not hasattr(self.agent_identity, field) or not getattr(self.agent_identity, field):
                logger.error(f"Identity integrity check failed - missing {field}")
                return False
        
        logger.info(f"✓ Identity verified: {self.agent_identity.agent_id} ({self.agent_identity.identity_hash[:8]}...)")
        return True
    
    async def _initialize_security_services(self) -> None:
        """Initialize security-critical services first."""
        config = self._ensure_config()
        
        # Initialize secrets service
        self.secrets_service = SecretsService(
            db_path=getattr(config.secrets, 'db_path', 'secrets.db') if hasattr(config, 'secrets') else 'secrets.db'
        )
        await self.secrets_service.start()
        
        # Initialize WA authentication system
        self.wa_auth_system = await initialize_authentication()
        logger.info("✓ Security services initialized")
    
    async def _verify_security_services(self) -> bool:
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
    
    async def _initialize_services(self) -> None:
        """Initialize all remaining core services."""
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
        self.llm_service = OpenAICompatibleClient(config.llm_services.openai, telemetry_service=self.telemetry_service)
        await self.llm_service.start()
        
        # Memory service already initialized in _initialize_memory_service
        # Secrets service already initialized in _initialize_security_services
        
        # Initialize ALL THREE REQUIRED audit services - they ALL receive events through the sink
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
            tags={"agent_profile": self.profile_name},
            retention_policy="raw",
            enable_file_backup=False,  # We already have file backup from service #1
            file_audit_service=None
        )
        await tsdb_audit.start()
        # Type cast to AuditService for proper typing
        self.audit_services.append(tsdb_audit)  # type: ignore[arg-type]
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
        
        # Secrets service already initialized in _initialize_security_services
        # WA auth system already initialized in _initialize_security_services
        
        # Initialize adaptive filter service
        self.adaptive_filter_service = AdaptiveFilterService(
            memory_service=self.memory_service,
            llm_service=self.llm_service
        )
        await self.adaptive_filter_service.start()
        
        # Initialize agent configuration service
        self.agent_config_service = AgentConfigService(
            memory_service=self.memory_service,
            wa_service=self.wa_auth_system.get_auth_service(),
            filter_service=self.adaptive_filter_service
        )
        await self.agent_config_service.start()
        
        # Initialize transaction orchestrator
        self.transaction_orchestrator = MultiServiceTransactionOrchestrator(
            service_registry=self.service_registry,
            action_sink=self.multi_service_sink,
            app_config=self.app_config
        )
        await self.transaction_orchestrator.start()
        
        archive_dir = getattr(config, "data_archive_dir", "data_archive")
        archive_hours = getattr(config, "archive_older_than_hours", 24)
        self.maintenance_service = DatabaseMaintenanceService(
            archive_dir_path=archive_dir,
            archive_older_than_hours=archive_hours
        )
    
    async def _verify_core_services(self) -> bool:
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
            if not self.audit_services or len(self.audit_services) != 3:
                logger.error(f"Expected 3 audit services, found {len(self.audit_services) if self.audit_services else 0}")
                return False
            
            logger.info("✓ All core services verified")
            return True
        except Exception as e:
            logger.error(f"Core services verification failed: {e}")
            return False
    
    async def _start_adapters(self) -> None:
        """Start all adapters."""
        await asyncio.gather(*(adapter.start() for adapter in self.adapters))
        logger.info(f"All {len(self.adapters)} adapters started")
    
    async def _final_verification(self) -> None:
        """Perform final system verification."""
        # Verify initialization status
        init_status = get_initialization_manager().get_status()
        
        if not init_status.get("complete"):
            raise RuntimeError("Initialization not complete")
        
        # Verify identity loaded
        if not self.agent_identity:
            raise RuntimeError("No agent identity established")
        
        # Log final status
        logger.info("=" * 60)
        logger.info("CIRIS Agent Pre-Wakeup Verification Complete")
        logger.info(f"Identity: {self.agent_identity.agent_id}")
        logger.info(f"Purpose: {self.agent_identity.core_profile.description}")
        logger.info(f"Capabilities: {len(self.agent_identity.allowed_capabilities)} allowed")
        logger.info(f"Services: {len(self.service_registry._services) if self.service_registry else 0} registered")
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
                
                auth_token = await self.wa_auth_system.create_adapter_token(adapter_type, adapter_info)
                
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
        
        if not self.service_registry:
            raise RuntimeError("Service registry not initialized")
            
        config = self._ensure_config()

        ethical_pdma = EthicalPDMAEvaluator(
            service_registry=self.service_registry,
            model_name=self.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            sink=self.multi_service_sink,
        )

        csdma = CSDMAEvaluator(
            service_registry=self.service_registry,
            model_name=self.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.csdma_overrides if self.profile else None,
            sink=self.multi_service_sink,
        )

        # Create faculty manager and epistemic faculties
        from ciris_engine.faculties.faculty_manager import FacultyManager
        faculty_manager = FacultyManager(self.service_registry)
        faculty_manager.create_default_faculties()
        
        action_pdma = ActionSelectionPDMAEvaluator(
            service_registry=self.service_registry,
            model_name=self.llm_service.model_name,
            max_retries=config.llm_services.openai.max_retries,
            prompt_overrides=self.profile.action_selection_pdma_overrides if self.profile else None,
            sink=self.multi_service_sink,
            faculties=faculty_manager.faculties,  # Pass faculties for enhanced evaluation
        )

        dsdma = await create_dsdma_from_profile(
            self.profile,
            self.service_registry,
            model_name=self.llm_service.model_name,
            sink=self.multi_service_sink,
        )
        
        guardrail_registry = GuardrailRegistry()
        guardrail_registry.register_guardrail(
            "entropy",
            EntropyGuardrail(self.service_registry, config.guardrails, self.llm_service.model_name, self.multi_service_sink),
            priority=0,
        )
        guardrail_registry.register_guardrail(
            "coherence",
            CoherenceGuardrail(self.service_registry, config.guardrails, self.llm_service.model_name, self.multi_service_sink),
            priority=1,
        )
        guardrail_registry.register_guardrail(
            "optimization_veto",
            OptimizationVetoGuardrail(self.service_registry, config.guardrails, self.llm_service.model_name, self.multi_service_sink),
            priority=2,
        )
        guardrail_registry.register_guardrail(
            "epistemic_humility",
            EpistemicHumilityGuardrail(self.service_registry, config.guardrails, self.llm_service.model_name, self.multi_service_sink),
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
            shutdown_callback=lambda: self.request_shutdown(
                "Handler requested shutdown due to critical service failure"
            ),
            multi_service_sink=self.multi_service_sink,
            memory_service=self.memory_service,
            audit_service=self.audit_service,
        )
        
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
            },
            startup_channel_id=self.startup_channel_id,
            runtime=self,  # Pass runtime reference for preload tasks
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
                    service_type="audit",
                    provider=audit_service,
                    priority=priority,
                    capabilities=capabilities,
                    metadata={"audit_type": service_name}
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
                capabilities=["generate_structured_response"]
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
                capabilities=["transaction_coordination", "service_routing", "health_monitoring", "audit_broadcast"]
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
        logger.info("Shutting down CIRIS Runtime...")
        
        # Preserve agent consciousness if identity exists
        if hasattr(self, 'agent_identity') and self.agent_identity:
            await self._preserve_shutdown_consciousness()
        
        logger.info("Initiating shutdown sequence for CIRIS Runtime...")
        self._ensure_shutdown_event()
        if self._shutdown_event:
            self._shutdown_event.set() # Ensure event is set for any waiting components

        if self.agent_processor:
            logger.debug("Stopping agent processor...")
            await self.agent_processor.stop_processing()
            logger.debug("Agent processor stopped.")
    
    async def _preserve_shutdown_consciousness(self) -> None:
        """Preserve agent state for future reactivation."""
        try:
            from ciris_engine.schemas.identity_schemas_v1 import ShutdownContext
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
            
            # Create shutdown context
            shutdown_context = ShutdownContext(
                reason=self._shutdown_reason or "Graceful shutdown",
                final_state={
                    "active_tasks": persistence.count_active_tasks(),
                    "pending_thoughts": persistence.count_pending_thoughts(),
                    "runtime_duration": (datetime.now(timezone.utc) - self._start_time).total_seconds()
                        if hasattr(self, '_start_time') else 0
                },
                pending_tasks=[],  # TODO: Gather actual pending tasks
                deferred_thoughts=[],  # TODO: Gather deferred thoughts
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Create memory node for shutdown
            shutdown_node = GraphNode(
                id=f"shutdown_{datetime.now(timezone.utc).isoformat()}",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY,
                attributes={
                    "shutdown_context": shutdown_context.model_dump(),
                    "identity_hash": self.agent_identity.identity_hash,
                    "reactivation_count": self.agent_identity.core_profile.reactivation_count
                }
            )
            
            # Store in memory service
            if self.memory_service:
                await self.memory_service.memorize(shutdown_node)
                logger.info(f"Preserved shutdown consciousness: {shutdown_node.id}")
                
                # Update identity with shutdown memory reference
                self.agent_identity.core_profile.last_shutdown_memory = shutdown_node.id
                self.agent_identity.core_profile.reactivation_count += 1
                
                # Save updated identity
                persistence.save_agent_identity(self.agent_identity.model_dump())
                
        except Exception as e:
            logger.error(f"Failed to preserve shutdown consciousness: {e}")
            
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
        
        await asyncio.gather(
            *[s.stop() for s in services_to_stop if s],
            return_exceptions=True
        )
        
        if self.service_registry:
            self.service_registry.clear_all()
            self.service_registry = None
        
        logger.info("CIRIS Runtime shutdown complete")
