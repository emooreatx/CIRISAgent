"""Runtime control service for processor and adapter management."""
import logging
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Dict, Any
from datetime import timezone

if TYPE_CHECKING:
    from ciris_engine.logic.services.graph.config_service import GraphConfigService

from ciris_engine.protocols.services import RuntimeControlService as RuntimeControlServiceProtocol
from ciris_engine.logic.runtime.adapter_manager import RuntimeAdapterManager
from ciris_engine.logic.adapters.base import Service
# GraphConfigService is injected via dependency injection to avoid circular imports

from ciris_engine.schemas.services.core import ServiceStatus, ServiceCapabilities
from ciris_engine.schemas.services.core.runtime import (
    ProcessorStatus, ProcessorQueueStatus, AdapterInfo, ConfigBackup,
    ServiceRegistryInfo, CircuitBreakerResetResult, ServiceHealthStatus,
    ServiceSelectionExplanation, RuntimeEvent, ConfigReloadResult,
    ProcessorControlResponse, AdapterOperationResponse, RuntimeStatusResponse,
    RuntimeStateSnapshot, ConfigSnapshot, ConfigOperationResponse, ConfigValidationResponse,
    ConfigBackupResponse, ConfigScope, ConfigValidationLevel,
    AdapterStatus
)
from ciris_engine.schemas.services.core.runtime_config import (
    ServiceHealthReport
)

from ciris_engine.protocols.services import TimeServiceProtocol
from ciris_engine.schemas.services.shutdown import (
    WASignedCommand, EmergencyShutdownStatus, KillSwitchConfig
)

logger = logging.getLogger(__name__)

class RuntimeControlService(Service, RuntimeControlServiceProtocol):
    """Service for runtime control of processor, adapters, and configuration."""

    def __init__(
        self,
        runtime: Optional[Any] = None,
        adapter_manager: Optional[RuntimeAdapterManager] = None,
        config_manager: Optional[Any] = None,
        time_service: Optional[TimeServiceProtocol] = None
    ) -> None:
        super().__init__()  # Initialize Service base class
        self.runtime = runtime
        self._time_service = time_service
        self.adapter_manager = adapter_manager
        if not self.adapter_manager and runtime:
            # Ensure we have a time service before creating adapter manager
            if self._time_service is None:
                from ciris_engine.logic.services.lifecycle.time import TimeService
                self._time_service = TimeService()
            self.adapter_manager = RuntimeAdapterManager(runtime, self._time_service)
        self.config_manager: Optional["GraphConfigService"] = config_manager
        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()
        self._processor_status = ProcessorStatus.RUNNING
        self._start_time = self._now()
        self._last_config_change: Optional[datetime] = None
        self._events_history: List[RuntimeEvent] = []

        # Kill switch configuration
        self._kill_switch_config = KillSwitchConfig(
            enabled=True,
            trust_tree_depth=3,
            allow_relay=True,
            max_shutdown_time_ms=30000,
            command_expiry_seconds=300,
            require_reason=True,
            log_to_audit=True,
            allow_override=False
        )
        self._wa_public_keys: Dict[str, Any] = {}  # wa_id -> Ed25519PublicKey

    def _now(self) -> datetime:
        """Get current time, with fallback if time service not available."""
        if self._time_service:
            return self._time_service.now()
        return datetime.now(timezone.utc)
    
    def _get_config_manager(self) -> "GraphConfigService":
        """Get config manager with lazy initialization to avoid circular imports."""
        if self.config_manager is None:
            # Config manager must be injected, cannot create without dependencies
            raise RuntimeError("Config manager not available - must be injected via dependency injection")
        return self.config_manager

    async def _initialize(self) -> None:
        """Initialize the runtime control service."""
        try:
            # Config manager is already initialized by service initializer
            logger.info("Runtime control service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize runtime control service: {e}")
            raise

    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        try:
            _start_time = self._now()

            # Get the agent processor from runtime
            if not self.runtime or not hasattr(self.runtime, 'agent_processor'):
                return ProcessorControlResponse(
                    success=False,
                    processor_name="agent",
                    operation="single_step",
                    new_status=self._processor_status,
                    error="Agent processor not available"
                )

            result = await self.runtime.agent_processor.single_step()
            await self._record_event("processor_control", "single_step", success=True, result=result)

            return ProcessorControlResponse(
                success=True,
                processor_name="agent",
                operation="single_step",
                new_status=self._processor_status,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to execute single step: {e}", exc_info=True)
            await self._record_event("processor_control", "single_step", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                processor_name="agent",
                operation="single_step",
                new_status=self._processor_status,
                error=str(e)
            )

    async def pause_processing(self) -> ProcessorControlResponse:
        """Pause the processor."""
        try:
            _start_time = self._now()

            # Get the agent processor from runtime
            if not self.runtime or not hasattr(self.runtime, 'agent_processor'):
                return ProcessorControlResponse(
                    success=False,
                    processor_name="agent",
                    operation="pause",
                    new_status=self._processor_status,
                    error="Agent processor not available"
                )

            success = await self.runtime.agent_processor.pause_processing()
            if success:
                self._processor_status = ProcessorStatus.PAUSED
            await self._record_event("processor_control", "pause", success=success)

            return ProcessorControlResponse(
                success=True,
                processor_name="agent",
                operation="pause",
                new_status=self._processor_status,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to pause processing: {e}", exc_info=True)
            await self._record_event("processor_control", "pause", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                processor_name="agent",
                operation="pause",
                new_status=self._processor_status,
                error=str(e)
            )

    async def resume_processing(self) -> ProcessorControlResponse:
        """Resume the processor."""
        try:
            _start_time = self._now()

            # Get the agent processor from runtime
            if not self.runtime or not hasattr(self.runtime, 'agent_processor'):
                return ProcessorControlResponse(
                    success=False,
                    processor_name="agent",
                    operation="resume",
                    new_status=self._processor_status,
                    error="Agent processor not available"
                )

            success = await self.runtime.agent_processor.resume_processing()
            if success:
                self._processor_status = ProcessorStatus.RUNNING
            await self._record_event("processor_control", "resume", success=success)

            return ProcessorControlResponse(
                success=True,
                processor_name="agent",
                operation="resume",
                new_status=self._processor_status,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to resume processing: {e}", exc_info=True)
            await self._record_event("processor_control", "resume", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                processor_name="agent",
                operation="resume",
                new_status=self._processor_status,
                error=str(e)
            )

    async def get_processor_queue_status(self) -> ProcessorQueueStatus:
        """Get processor queue status."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'agent_processor'):
                return ProcessorQueueStatus(
                    processor_name="unknown",
                    queue_size=0,
                    max_size=0,
                    processing_rate=0.0,
                    average_latency_ms=0.0,
                    oldest_message_age_seconds=None
                )

            # Get queue status from agent processor
            queue_status = self.runtime.agent_processor.get_queue_status()

            await self._record_event("processor_query", "queue_status", success=True)

            return ProcessorQueueStatus(
                processor_name="agent",
                queue_size=queue_status.pending_thoughts + queue_status.pending_tasks,
                max_size=1000,  # Default max size
                processing_rate=1.0,  # Would need to calculate from metrics
                average_latency_ms=0.0,  # Would need to calculate from metrics
                oldest_message_age_seconds=None
            )
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}", exc_info=True)
            await self._record_event("processor_query", "queue_status", success=False, error=str(e))
            return ProcessorQueueStatus(
                processor_name="agent",
                queue_size=0,
                max_size=0,
                processing_rate=0.0,
                average_latency_ms=0.0,
                oldest_message_age_seconds=None
            )

    async def shutdown_runtime(self, reason: str = "Runtime shutdown requested") -> ProcessorControlResponse:
        """Shutdown the entire runtime system."""
        try:
            _start_time = self._now()

            logger.critical(f"RUNTIME SHUTDOWN INITIATED: {reason}")

            # Record the shutdown event
            await self._record_event("processor_control", "shutdown", success=True, result={"reason": reason})

            # Request global shutdown through the shutdown service
            if self.runtime and hasattr(self.runtime, 'service_registry'):
                shutdown_service = self.runtime.service_registry.get_service('ShutdownService')
                if shutdown_service:
                    shutdown_service.request_shutdown(f"Runtime control: {reason}")
                else:
                    logger.error("ShutdownService not available in registry")

            # Set processor status to stopped
            self._processor_status = ProcessorStatus.STOPPED

            return ProcessorControlResponse(
                success=True,
                processor_name="agent",
                operation="shutdown",
                new_status=self._processor_status,
                error=None
            )

        except Exception as e:
            logger.error(f"Failed to initiate shutdown: {e}", exc_info=True)
            await self._record_event("processor_control", "shutdown", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                processor_name="agent",
                operation="shutdown",
                new_status=self._processor_status,
                error=str(e)
            )

    async def handle_emergency_shutdown(self, command: WASignedCommand) -> EmergencyShutdownStatus:
        """
        Handle WA-authorized emergency shutdown command.

        Verifies WA signature and calls the shutdown service immediately.

        Args:
            command: Signed emergency shutdown command from WA

        Returns:
            Status of emergency shutdown process
        """
        logger.critical(f"EMERGENCY SHUTDOWN COMMAND RECEIVED from WA {command.wa_id}")

        # Initialize status
        now = self._now()
            
        status = EmergencyShutdownStatus(
            command_received=now,
            command_verified=False,
            verification_error=None,
            shutdown_initiated=None,
            data_persisted=False,
            final_message_sent=False,
            shutdown_completed=None,
            exit_code=None
        )

        try:
            # Verify WA signature
            if not self._verify_wa_signature(command):
                status.command_verified = False
                status.verification_error = "Invalid WA signature"
                logger.error(f"Emergency shutdown rejected: Invalid signature from {command.wa_id}")
                return status

            status.command_verified = True
            status.shutdown_initiated = self._now()

            # Record emergency event
            await self._record_event(
                "emergency_shutdown",
                "command_verified",
                success=True,
                result={
                    "wa_id": command.wa_id,
                    "command_id": command.command_id,
                    "reason": command.reason
                }
            )

            # Call the existing shutdown mechanism
            # This will trigger all registered shutdown handlers
            shutdown_reason = f"WA EMERGENCY SHUTDOWN: {command.reason} (WA: {command.wa_id})"

            # Get shutdown service from registry if available
            if self.runtime and hasattr(self.runtime, 'service_registry'):
                shutdown_service = self.runtime.service_registry.get_service('ShutdownService')
                if shutdown_service:
                    shutdown_service.request_shutdown(shutdown_reason)
                    status.shutdown_completed = self._now()
                    status.exit_code = 0
                    logger.info("Emergency shutdown delegated to ShutdownService")
                    return status

            # Fallback to direct shutdown
            await self.shutdown_runtime(shutdown_reason)
            status.shutdown_completed = self._now()
            status.exit_code = 0

            return status

        except Exception as e:
            logger.critical(f"Emergency shutdown failed: {e}")
            status.verification_error = str(e)
            status.shutdown_completed = self._now()
            status.exit_code = 1
            return status

    def _verify_wa_signature(self, command: WASignedCommand) -> bool:
        """
        Verify the WA signature on an emergency command.

        Args:
            command: The signed command to verify

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Check if WA is authorized
            if command.wa_id not in self._wa_public_keys:
                logger.error(f"WA {command.wa_id} not in authorized keys")
                return False

            # Get public key
            public_key = self._wa_public_keys[command.wa_id]

            # Reconstruct signed data (canonical form)
            signed_data = "|".join([
                f"command_id:{command.command_id}",
                f"command_type:{command.command_type}",
                f"wa_id:{command.wa_id}",
                f"issued_at:{command.issued_at.isoformat()}",
                f"reason:{command.reason}"
            ])

            if command.target_agent_id:
                signed_data += f"|target_agent_id:{command.target_agent_id}"

            # Verify signature
            from cryptography.exceptions import InvalidSignature
            try:
                signature_bytes = bytes.fromhex(command.signature)
                public_key.verify(signature_bytes, signed_data.encode('utf-8'))
                return True
            except InvalidSignature:
                logger.error("Invalid signature on emergency command")
                return False

        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    def _configure_kill_switch(self, config: KillSwitchConfig) -> None:
        """
        Configure the emergency kill switch.

        Args:
            config: Kill switch configuration including root WA keys
        """
        self._kill_switch_config = config

        # Parse and store WA public keys
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        self._wa_public_keys.clear()
        for key_pem in config.root_wa_public_keys:
            try:
                public_key = serialization.load_pem_public_key(key_pem.encode('utf-8'))
                if isinstance(public_key, ed25519.Ed25519PublicKey):
                    # Extract WA ID from comment or use hash
                    wa_id = self._extract_wa_id_from_pem(key_pem)
                    self._wa_public_keys[wa_id] = public_key
            except Exception as e:
                logger.error(f"Failed to load WA public key: {e}")

        logger.info(f"Kill switch configured with {len(self._wa_public_keys)} root WA keys")

    def _extract_wa_id_from_pem(self, key_pem: str) -> str:
        """Extract WA ID from PEM comment or generate from hash."""
        for line in key_pem.split('\n'):
            if line.startswith('# WA-ID:'):
                return line.split(':', 1)[1].strip()

        # Fallback to hash
        import hashlib
        return hashlib.sha256(key_pem.encode()).hexdigest()[:16]

    # Adapter Management Methods
    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: Optional[str] = None,
        config: Optional[Dict[str, object]] = None,
        auto_start: bool = True
    ) -> AdapterOperationResponse:
        """Load a new adapter instance."""
        # AdapterStatus is already imported at module level

        # Lazy initialization of adapter_manager if needed
        if not self.adapter_manager and self.runtime:
            if self._time_service is None:
                from ciris_engine.logic.services.lifecycle.time import TimeService
                self._time_service = TimeService()
            self.adapter_manager = RuntimeAdapterManager(self.runtime, self._time_service)
            logger.info("Lazy-initialized adapter_manager in load_adapter")

        if not self.adapter_manager:
            return AdapterOperationResponse(
                success=False,
                timestamp=self._now(),
                adapter_id=adapter_id or "unknown",
                adapter_type=adapter_type,
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )

        # Convert config dict to proper type if needed
        adapter_config = config if config else {}
        result = await self.adapter_manager.load_adapter(adapter_type, adapter_id or "", adapter_config)

        return AdapterOperationResponse(
            success=result.success,
            adapter_id=result.adapter_id,
            adapter_type=adapter_type,
            timestamp=self._now(),
            status=AdapterStatus.RUNNING if result.success else AdapterStatus.ERROR,
            error=result.error
        )

    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterOperationResponse:
        """Unload an adapter instance."""
        # AdapterStatus is already imported at module level

        # Lazy initialization of adapter_manager if needed
        if not self.adapter_manager and self.runtime:
            if self._time_service is None:
                from ciris_engine.logic.services.lifecycle.time import TimeService
                self._time_service = TimeService()
            self.adapter_manager = RuntimeAdapterManager(self.runtime, self._time_service)
            logger.info("Lazy-initialized adapter_manager in unload_adapter")

        if not self.adapter_manager:
            return AdapterOperationResponse(
                success=False,
                timestamp=self._now(),
                adapter_id=adapter_id or "unknown",
                adapter_type="unknown",
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )

        # Call adapter manager (note: it doesn't use force parameter)
        result = await self.adapter_manager.unload_adapter(adapter_id)

        # Convert AdapterOperationResult to AdapterOperationResponse
        return AdapterOperationResponse(
            success=result.success,
            adapter_id=result.adapter_id,
            adapter_type=result.adapter_type or "unknown",
            timestamp=self._now(),
            status=AdapterStatus.STOPPED if result.success else AdapterStatus.ERROR,
            error=result.error
        )

    async def list_adapters(self) -> List[AdapterInfo]:
        """List all loaded adapters including bootstrap adapters."""
        # Lazy initialization of adapter_manager if needed
        if not self.adapter_manager and self.runtime:
            if self._time_service is None:
                from ciris_engine.logic.services.lifecycle.time import TimeService
                self._time_service = TimeService()
            self.adapter_manager = RuntimeAdapterManager(self.runtime, self._time_service)
            logger.info("Lazy-initialized adapter_manager in list_adapters")
        
        adapters_list = []
        
        # First, add bootstrap adapters from runtime
        if self.runtime and hasattr(self.runtime, 'adapters'):
            for adapter in self.runtime.adapters:
                # Get adapter type from class name
                adapter_type = adapter.__class__.__name__.lower().replace('platform', '').replace('adapter', '')
                
                # Skip creating bootstrap entries for adapters that are managed by adapter_manager
                # Only create bootstrap entries for adapters that were started with --adapter flag
                if adapter_type == 'discord' and self.adapter_manager and any(
                    a.adapter_type == 'discord' for a in await self.adapter_manager.list_adapters()
                ):
                    continue
                    
                adapter_id = f"{adapter_type}_bootstrap"
                
                # Check if adapter has tools
                tools = []
                if hasattr(adapter, 'tool_service') and adapter.tool_service:
                    try:
                        if hasattr(adapter.tool_service, 'list_tools'):
                            tool_names = await adapter.tool_service.list_tools()
                            for tool_name in tool_names:
                                tool_info = {"name": tool_name, "description": f"{tool_name} tool"}
                                if hasattr(adapter.tool_service, 'get_tool_schema'):
                                    schema = await adapter.tool_service.get_tool_schema(tool_name)
                                    if schema:
                                        tool_info["schema"] = schema.dict() if hasattr(schema, 'dict') else schema
                                tools.append(tool_info)
                    except Exception as e:
                        logger.debug(f"Could not get tools from {adapter_type}: {e}")
                
                # Create adapter info
                adapters_list.append(AdapterInfo(
                    adapter_id=adapter_id or "unknown",
                    adapter_type=adapter_type,
                    status=AdapterStatus.RUNNING,  # Bootstrap adapters are always running
                    started_at=self._start_time,  # Use service start time
                    messages_processed=0,  # Tracked via telemetry service
                    error_count=0,
                    last_error=None,
                    tools=tools  # Include tools information
                ))
        
        # Then add adapters from adapter_manager
        if self.adapter_manager:
            adapters_raw = await self.adapter_manager.list_adapters()
            for adapter_status in adapters_raw:
                # AdapterStatus from adapter_manager already has the right fields
                # Convert is_running to status enum
                if adapter_status.is_running:
                    status = AdapterStatus.RUNNING
                else:
                    status = AdapterStatus.STOPPED

                adapters_list.append(AdapterInfo(
                    adapter_id=adapter_status.adapter_id,
                    adapter_type=adapter_status.adapter_type,
                    status=status,
                    started_at=adapter_status.loaded_at,
                    messages_processed=adapter_status.metrics.get('messages_processed', 0) if adapter_status.metrics and hasattr(adapter_status.metrics, 'get') else 0,
                    error_count=adapter_status.metrics.get('errors_count', 0) if adapter_status.metrics and hasattr(adapter_status.metrics, 'get') else 0,
                    last_error=adapter_status.metrics.get('last_error') if adapter_status.metrics and hasattr(adapter_status.metrics, 'get') else None,
                    tools=adapter_status.tools if hasattr(adapter_status, 'tools') else None
                ))

        return adapters_list

    async def get_adapter_info(self, adapter_id: str) -> Optional[AdapterInfo]:
        """Get detailed information about a specific adapter."""
        # Lazy initialization of adapter_manager if needed
        if not self.adapter_manager and self.runtime:
            if self._time_service is None:
                from ciris_engine.logic.services.lifecycle.time import TimeService
                self._time_service = TimeService()
            self.adapter_manager = RuntimeAdapterManager(self.runtime, self._time_service)
            logger.info("Lazy-initialized adapter_manager in get_adapter_info")
        
        if not self.adapter_manager:
            return None

        info = await self.adapter_manager.get_adapter_info(adapter_id)
        if "error" in info:
            return None

        # Map the status string to AdapterStatus enum
        status_str = info.get("status", "unknown")
        try:
            status = AdapterStatus(status_str)
        except ValueError:
            status = AdapterStatus.ERROR

        return AdapterInfo(
            adapter_id=info.get("adapter_id", adapter_id),
            adapter_type=info.get("adapter_type", ""),
            status=status,
            started_at=info.get("loaded_at", self._now()),
            messages_processed=info.get("metrics", {}).get("messages_processed", 0),
            error_count=info.get("metrics", {}).get("errors_count", 0),
            last_error=info.get("metrics", {}).get("last_error"),
            tools=None
        )

    # Configuration Management Methods
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> ConfigSnapshot:
        """Get configuration value(s)."""
        try:
            # Get all configs or specific config
            config_values: Dict[str, Any]
            if path:
                config_node = await self._get_config_manager().get_config(path)
                if config_node:
                    config_values = {path: config_node.value}
                else:
                    config_values = {}
            else:
                # list_configs returns Dict[str, Union[str, int, float, bool, List, Dict]]
                config_values = await self._get_config_manager().list_configs()

            # Determine sensitive keys
            sensitive_keys = []
            if not include_sensitive:
                # Mark which keys would be sensitive
                from ciris_engine.schemas.api.config_security import ConfigSecurity
                for key in config_values.keys():
                    if ConfigSecurity.is_sensitive(key):
                        sensitive_keys.append(key)

            return ConfigSnapshot(
                configs=config_values,
                version=self.config_version if hasattr(self, 'config_version') else "1.0.0",
                sensitive_keys=sensitive_keys,
                metadata={
                    "path_filter": path,
                    "include_sensitive": include_sensitive
                }
            )
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return ConfigSnapshot(
                configs={},
                version="unknown",
                metadata={"error": str(e)}
            )

    async def update_config(
        self,
        path: str,
        value: object,
        scope: str = "runtime",
        validation_level: str = "full",
        reason: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update a configuration value."""
        try:
            # Convert string parameters to enums
            config_scope = ConfigScope(scope) if isinstance(scope, str) else scope
            config_validation = ConfigValidationLevel(validation_level) if isinstance(validation_level, str) else validation_level

            # GraphConfigService uses set_config, not update_config_value
            # Convert object to appropriate type
            config_value = value if isinstance(value, (str, int, float, bool, list, dict)) else str(value)
            await self._get_config_manager().set_config(path, config_value, updated_by="RuntimeControlService")
            result = ConfigOperationResponse(
                success=True,
                operation="update_config",
                config_path=path,
                details={
                    "scope": scope,
                    "validation_level": validation_level,
                    "reason": reason,
                    "timestamp": self._now().isoformat()
                },
                error=None
            )
            if result.success:
                self._last_config_change = self._now()
            return result
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="update_config",
                config_path=path,
                details={"timestamp": self._now().isoformat()},
                error=str(e)
            )

    async def validate_config(
        self,
        config_data: Dict[str, object],
        config_path: Optional[str] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        try:
            # GraphConfigService doesn't have validate_config, do basic validation
            return ConfigValidationResponse(
                valid=True,
                validation_level=ConfigValidationLevel.SYNTAX,
                errors=[],
                warnings=[],
                suggestions=[]
            )
        except Exception as e:
            logger.error(f"Failed to validate config: {e}")
            return ConfigValidationResponse(
                valid=False,
                validation_level=ConfigValidationLevel.SYNTAX,
                errors=[str(e)],
                warnings=[],
                suggestions=[]
            )

    async def backup_config(
        self,
        backup_name: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Create a configuration backup."""
        try:
            # GraphConfigService doesn't have backup_config, store as special config
            all_configs = await self._get_config_manager().list_configs()
            backup_key = f"backup_{backup_name or self._now().strftime('%Y%m%d_%H%M%S')}"
            await self._get_config_manager().set_config(
                backup_key,
                all_configs,
                updated_by="RuntimeControlService"
            )
            # Create a simple namespace object with the required attributes
            from types import SimpleNamespace
            result = SimpleNamespace(
                success=True,
                backup_id=backup_key,
                backup_name=backup_name,
                timestamp=self._now(),
                size_bytes=len(str(all_configs))
            )
            # Convert ConfigBackupResponse to ConfigOperationResponse
            return ConfigOperationResponse(
                success=result.success if hasattr(result, 'success') else True,
                operation="backup_config",
                config_path="config",
                details={
                    "timestamp": result.timestamp.isoformat() if hasattr(result, 'timestamp') else self._now().isoformat(),
                    "backup_id": result.backup_id if hasattr(result, 'backup_id') else None,
                    "backup_name": result.backup_name if hasattr(result, 'backup_name') else backup_name,
                    "size_bytes": result.size_bytes if hasattr(result, 'size_bytes') else None
                },
                error=result.error if hasattr(result, 'error') else None
            )
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="backup_config",
                config_path="config",
                details={"timestamp": self._now().isoformat()},
                error=str(e)
            )

    async def restore_config(
        self,
        backup_name: str
    ) -> ConfigOperationResponse:
        """Restore configuration from backup."""
        try:
            # Get backup config and restore all values
            backup_config = await self._get_config_manager().get_config(backup_name)
            if not backup_config:
                raise ValueError(f"Backup '{backup_name}' not found")
            
            # Restore each config value  
            # ConfigValue is a special type, need to extract the actual value
            backup_data = backup_config.value
            actual_backup: Dict[str, Any] = {}
            
            # Extract actual value from ConfigValue wrapper
            if hasattr(backup_data, 'dict_value') and backup_data.dict_value:
                actual_backup = backup_data.dict_value
            elif hasattr(backup_data, 'to_dict'):
                actual_backup = backup_data.to_dict()
            else:
                # Try to convert directly
                try:
                    actual_backup = dict(backup_data) if backup_data else {}
                except:
                    raise ValueError("Cannot extract backup data from config")
            
            for key, value in actual_backup.items():
                if not key.startswith("backup_"):  # Don't restore backups
                    # Ensure value is proper type for set_config
                    config_val = value if isinstance(value, (str, int, float, bool, list, dict)) else str(value)
                    await self._get_config_manager().set_config(key, config_val, "RuntimeControlService")
            
            result = {"success": True, "message": f"Restored from backup {backup_name}"}

            # Convert to ConfigOperationResponse
            return ConfigOperationResponse(
                success=bool(result.get("success", False)),
                operation="restore_config",
                config_path="config",
                details={
                    "backup_name": backup_name,
                    "timestamp": self._now().isoformat(),
                    "message": result.get("message", "Configuration restored from backup")
                },
                error=None
            )
        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="restore_config",
                config_path="config",
                details={
                    "backup_name": backup_name,
                    "timestamp": self._now().isoformat()
                },
                error=str(e)
            )

    async def list_config_backups(self) -> List[ConfigBackup]:
        """List available configuration backups."""
        try:
            # List all backup configs
            all_configs = await self._get_config_manager().list_configs(prefix="backup_")
            backups = []
            for key, value in all_configs.items():
                backup = ConfigBackup(
                    backup_id=key,
                    created_at=self._now(),  # Would need to store this in config
                    config_version="1.0.0",
                    size_bytes=len(str(value)),
                    path=key,
                    description=None
                )
                backups.append(backup)
            return backups
        except Exception as e:
            logger.error(f"Failed to list config backups: {e}")
            return []

    async def get_runtime_status(self) -> RuntimeStatusResponse:
        """Get current runtime status."""
        try:
            current_time = self._now()
            uptime = (current_time - self._start_time).total_seconds()

            # Get adapter information
            adapters = []
            if self.adapter_manager:
                adapters = await self.adapter_manager.list_adapters()
            _active_adapters = [a.adapter_id for a in adapters if a.is_running]
            _loaded_adapters = [a.adapter_id for a in adapters]

            # Agent identity is now stored in graph, not profiles
            _current_profile = "identity-based"

            return RuntimeStatusResponse(
                is_running=self._processor_status == ProcessorStatus.RUNNING,
                uptime_seconds=uptime,
                processor_count=1,  # Single agent processor
                adapter_count=len(adapters),
                total_messages_processed=0,  # Would need to track this
                current_load=0.0  # Would need to calculate this
            )

        except Exception as e:
            logger.error(f"Failed to get runtime status: {e}")
            return RuntimeStatusResponse(
                is_running=False,
                uptime_seconds=0.0,
                processor_count=1,
                adapter_count=0,
                total_messages_processed=0,
                current_load=0.0
            )

    async def get_runtime_snapshot(self) -> RuntimeStateSnapshot:
        """Get complete runtime state snapshot."""
        try:
            current_time = self._now()
            uptime = (current_time - self._start_time).total_seconds()

            # Get runtime status
            runtime_status = await self.get_runtime_status()
            
            # Get processor queue status
            processor_queue = await self.get_processor_queue_status()
            processors = [processor_queue]
            
            # Get adapters
            adapters = await self.list_adapters()
            
            # Get config version
            config_snapshot = await self.get_config()
            config_version = config_snapshot.version
            
            # Get health summary
            health_summary = await self.get_service_health_status()
            
            return RuntimeStateSnapshot(
                timestamp=current_time,
                runtime_status=runtime_status,
                processors=processors,
                adapters=adapters,
                config_version=config_version,
                health_summary=health_summary
            )

        except Exception as e:
            logger.error(f"Failed to get runtime snapshot: {e}")
            raise

    async def _get_service_registry_info(self, handler: Optional[str] = None, service_type: Optional[str] = None) -> Dict[str, Any]:
        """Get information about registered services in the service registry."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                # Return a valid ServiceRegistryInfo-like dict
                return {
                    "total_services": 0,
                    "services_by_type": {},
                    "handlers": {},
                    "healthy_services": 0,
                    "circuit_breaker_states": {},
                    "error": "Service registry not available"
                }

            info = self.runtime.service_registry.get_provider_info(handler, service_type)
            # Ensure we always return a dict
            if isinstance(info, dict):
                return info
            else:
                # Return the info as-is if it's a dict, otherwise wrap it
                return info if isinstance(info, dict) else {"data": info}
        except Exception as e:
            logger.error(f"Failed to get service registry info: {e}")
            return {"error": str(e)}

    async def update_service_priority(
        self,
        provider_name: str,
        new_priority: str,
        new_priority_group: Optional[int] = None,
        new_strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update service provider priority and selection strategy."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry'):
                return {"success": False, "error": "Service registry not available"}

            registry = self.runtime.service_registry

            # Import the Priority and SelectionStrategy enums
            from ciris_engine.logic.registries.base import Priority, SelectionStrategy

            # Validate priority string
            try:
                new_priority_enum = Priority[new_priority.upper()]
            except KeyError:
                valid_priorities = [p.name for p in Priority]
                return {
                    "success": False,
                    "error": f"Invalid priority '{new_priority}'. Valid priorities: {valid_priorities}"
                }

            # Validate selection strategy if provided
            new_strategy_enum = None
            if new_strategy:
                try:
                    new_strategy_enum = SelectionStrategy[new_strategy.upper()]
                except KeyError:
                    valid_strategies = [s.name for s in SelectionStrategy]
                    return {
                        "success": False,
                        "error": f"Invalid strategy '{new_strategy}'. Valid strategies: {valid_strategies}"
                    }

            # Find the provider in handler-specific services
            provider_found = False
            updated_info = {}

            # Check in the main services registry
            for service_type, providers in registry._services.items():
                for provider in providers:
                    if provider.name == provider_name:
                        provider_found = True
                        old_priority = provider.priority.name
                        old_priority_group = provider.priority_group
                        old_strategy = provider.strategy.name

                        # Update provider attributes
                        provider.priority = new_priority_enum
                        if new_priority_group is not None:
                            provider.priority_group = new_priority_group
                        if new_strategy_enum is not None:
                            provider.strategy = new_strategy_enum

                        # Re-sort providers by priority
                        providers.sort(key=lambda x: (x.priority_group, x.priority.value))

                        updated_info = {
                            "service_type": str(service_type),
                            "old_priority": old_priority,
                            "new_priority": provider.priority.name,
                            "old_priority_group": old_priority_group,
                            "new_priority_group": provider.priority_group,
                            "old_strategy": old_strategy,
                            "new_strategy": provider.strategy.name
                        }
                        break
                if provider_found:
                    break


            if not provider_found:
                return {
                    "success": False,
                    "error": f"Service provider '{provider_name}' not found in registry"
                }

            # Record the event
            await self._record_event(
                "service_management",
                "update_priority",
                success=True,
                result=updated_info
            )

            logger.info(
                f"Updated service provider '{provider_name}' priority from "
                f"{updated_info['old_priority']} to {updated_info['new_priority']}"
            )

            return {
                "success": True,
                "message": f"Successfully updated provider '{provider_name}' priority",
                "provider_name": provider_name,
                "changes": updated_info,
                "timestamp": self._now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to update service priority: {e}")
            await self._record_event(
                "service_management",
                "update_priority",
                success=False,
                error=str(e)
            )
            return {"success": False, "error": str(e)}

    async def reset_circuit_breakers(self, service_type: Optional[str] = None) -> Dict[str, Any]:
        """Reset circuit breakers for services."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return {"success": False, "error": "Service registry not available"}

            self.runtime.service_registry.reset_circuit_breakers()

            await self._record_event("service_management", "reset_circuit_breakers", True,
                                    result={"service_type": service_type})

            return {
                "success": True,
                "message": "Circuit breakers reset successfully",
                "timestamp": self._now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to reset circuit breakers: {e}")
            await self._record_event("service_management", "reset_circuit_breakers", False, error=str(e))
            return {"success": False, "error": str(e)}

    async def get_service_selection_explanation(self) -> ServiceSelectionExplanation:
        """Get explanation of service selection logic."""
        try:
            from ciris_engine.logic.registries.base import Priority, SelectionStrategy
            
            explanation = ServiceSelectionExplanation(
                overview="CIRIS uses a sophisticated multi-level service selection system with priority groups, priorities, and selection strategies.",
                priority_groups={
                    0: "Primary services - tried first",
                    1: "Secondary/backup services - used when primary unavailable", 
                    2: "Tertiary/fallback services - last resort (e.g., mock providers)"
                },
                priorities={
                    "CRITICAL": {"value": 0, "description": "Highest priority - always tried first within a group"},
                    "HIGH": {"value": 1, "description": "High priority services"},
                    "NORMAL": {"value": 2, "description": "Standard priority (default)"},
                    "LOW": {"value": 3, "description": "Low priority services"},
                    "FALLBACK": {"value": 9, "description": "Last resort services within a group"}
                },
                selection_strategies={
                    "FALLBACK": "First available strategy - try services in priority order until one succeeds",
                    "ROUND_ROBIN": "Load balancing - rotate through services to distribute load"
                },
                selection_flow=[
                    "1. Group services by priority_group (0, 1, 2...)",
                    "2. Within each group, sort by Priority (CRITICAL, HIGH, NORMAL, LOW, FALLBACK)",
                    "3. Apply the group's selection strategy (FALLBACK or ROUND_ROBIN)",
                    "4. Check if service is healthy (if health check available)",
                    "5. Check if circuit breaker is closed (not tripped)",
                    "6. Verify service has required capabilities",
                    "7. If all checks pass, use the service",
                    "8. If service fails, try next according to strategy",
                    "9. If all services in group fail, try next group"
                ],
                circuit_breaker_info={
                    "purpose": "Prevents repeated calls to failing services",
                    "states": {
                        "CLOSED": "Normal operation - service is available",
                        "OPEN": "Service is unavailable - too many recent failures",
                        "HALF_OPEN": "Testing if service has recovered"
                    },
                    "configuration": "Configurable failure threshold, timeout, and half-open test interval"
                },
                examples=[
                    {
                        "scenario": "LLM Service Selection",
                        "setup": "3 LLM providers: OpenAI (group 0, HIGH), Anthropic (group 0, NORMAL), MockLLM (group 1, NORMAL)",
                        "result": "System tries OpenAI first, then Anthropic, then MockLLM only if both group 0 providers fail"
                    },
                    {
                        "scenario": "Round Robin Load Balancing",
                        "setup": "2 Memory providers in group 0 with ROUND_ROBIN strategy",
                        "result": "Requests alternate between the two providers to distribute load"
                    }
                ],
                configuration_tips=[
                    "Use priority groups to separate production services (group 0) from fallback services (group 1+)",
                    "Set CRITICAL priority for essential services that should always be tried first",
                    "Use ROUND_ROBIN strategy for stateless services to distribute load",
                    "Configure circuit breakers with appropriate thresholds based on service reliability",
                    "Place mock/test services in higher priority groups (2+) to ensure they're only used as last resort"
                ]
            )
            
            await self._record_event("service_query", "get_selection_explanation", success=True)
            return explanation
            
        except Exception as e:
            logger.error(f"Failed to get service selection explanation: {e}")
            await self._record_event("service_query", "get_selection_explanation", success=False, error=str(e))
            # Return a minimal explanation on error
            return ServiceSelectionExplanation(
                overview="Error retrieving service selection explanation",
                priority_groups={},
                priorities={},
                selection_strategies={},
                selection_flow=[],
                circuit_breaker_info={},
                examples=[],
                configuration_tips=[]
            )

    async def get_service_health_status(self) -> ServiceHealthStatus:
        """Get health status of all registered services."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return ServiceHealthStatus(
                    overall_health="critical",
                    healthy_services=0,
                    unhealthy_services=0,
                    service_details={},
                    recommendations=["Service registry not available - check runtime initialization"]
                )

            registry_info = self.runtime.service_registry.get_provider_info()
            
            healthy_count = 0
            unhealthy_count = 0
            service_details = {}
            unhealthy_services_list = []
            healthy_services_list = []

            for handler, services in registry_info.get("handlers", {}).items():
                for service_type, providers in services.items():
                    for provider in providers:
                        service_key = f"{handler}.{service_type}.{provider['name']}"
                        cb_state = provider.get('circuit_breaker_state', 'closed')
                        is_healthy = cb_state == 'closed'

                        service_details[service_key] = {
                            "healthy": is_healthy,
                            "circuit_breaker_state": cb_state,
                            "priority": provider['priority'],
                            "priority_group": provider['priority_group'],
                            "strategy": provider['strategy']
                        }
                        
                        if is_healthy:
                            healthy_count += 1
                            healthy_services_list.append(service_key)
                        else:
                            unhealthy_count += 1
                            unhealthy_services_list.append(service_key)

            for service_type, providers in registry_info.get("global_services", {}).items():
                for provider in providers:
                    service_key = f"global.{service_type}.{provider['name']}"
                    cb_state = provider.get('circuit_breaker_state', 'closed')
                    is_healthy = cb_state == 'closed'

                    service_details[service_key] = {
                        "healthy": is_healthy,
                        "circuit_breaker_state": cb_state,
                        "priority": provider['priority'],
                        "priority_group": provider['priority_group'],
                        "strategy": provider['strategy']
                    }
                    
                    if is_healthy:
                        healthy_count += 1
                        healthy_services_list.append(service_key)
                    else:
                        unhealthy_count += 1
                        unhealthy_services_list.append(service_key)

            # Determine overall health
            overall_health = "healthy"
            recommendations = []
            
            if unhealthy_count > 0:
                if unhealthy_count > healthy_count:
                    overall_health = "unhealthy"
                    recommendations.append("Critical: More unhealthy services than healthy ones")
                else:
                    overall_health = "degraded"
                    recommendations.append(f"Warning: {unhealthy_count} services are unhealthy")
                    
                recommendations.append("Consider resetting circuit breakers for failed services")
                recommendations.append("Check service logs for error details")
            
            return ServiceHealthStatus(
                overall_health=overall_health,
                healthy_services=healthy_count,
                unhealthy_services=unhealthy_count,
                service_details=service_details,
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Failed to get service health status: {e}")
            return ServiceHealthStatus(
                overall_health="critical",
                healthy_services=0,
                unhealthy_services=0,
                service_details={},
                recommendations=[f"Critical error while checking service health: {str(e)}"]
            )

    async def _get_service_selection_explanation(self) -> ServiceSelectionExplanation:
        """Get explanation of how service selection works with priorities and strategies."""
        return ServiceSelectionExplanation(
            overview="Services are selected using a multi-tier priority system with configurable selection strategies",
            priority_groups={
                0: "Primary services - tried first",
                1: "Secondary services - used when primary unavailable",
                2: "Tertiary services - last resort options"
            },
            selection_strategies={
                "FALLBACK": "Use first available healthy service in priority order",
                "ROUND_ROBIN": "Rotate through services at same priority level"
            },
            examples=[{
                "scenario": "fallback_strategy",
                "description": "Two LLM services: OpenAI (CRITICAL) and LocalLLM (NORMAL)",
                "behavior": "Always try OpenAI first, fall back to LocalLLM if OpenAI fails"
            }, {
                "scenario": "round_robin_strategy",
                "description": "Three load-balanced API services all at NORMAL priority",
                "behavior": "Rotate requests: API1 -> API2 -> API3 -> API1 -> ..."
            }, {
                "scenario": "multi_group_example",
                "description": "Priority Group 0: Critical services, Priority Group 1: Backup services",
                "behavior": "Only use Group 1 services if all Group 0 services are unavailable"
            }],
            configuration_tips=[
                "Use priority groups to separate primary and backup services",
                "Set CRITICAL priority for essential services within a group",
                "Use ROUND_ROBIN strategy for load balancing similar services",
                "Configure circuit breakers to handle transient failures gracefully"
            ]
        )

    # Helper Methods
    async def _record_event(
        self,
        category: str,
        action: str,
        success: bool,
        result: Optional[Dict[str, object]] = None,
        error: Optional[str] = None
    ) -> None:
        """Record an event in the history."""
        try:
            event = RuntimeEvent(
                event_type=f"{category}:{action}",
                timestamp=self._now(),
                source="RuntimeControlService",
                details={"result": result, "success": success} if result else {"success": success},
                severity="error" if error else "info"
            )
            # Store additional fields in details since they're not in the schema
            if error:
                event.details["error"] = error

            self._events_history.append(event)

            if len(self._events_history) > 1000:
                self._events_history = self._events_history[-1000:]

        except Exception as e:
            logger.error(f"Failed to record event: {e}")

    def get_events_history(self, limit: int = 100) -> List[RuntimeEvent]:
        """Get recent events history."""
        return self._events_history[-limit:]

    # Legacy method to maintain compatibility
    async def _reload_config(self, config_path: Optional[str] = None) -> ConfigReloadResult:
        """Reload system configuration."""
        try:
            await self._record_event("config_reload", "reload", success=False, error="Legacy method - use specific config operations instead")

            return ConfigReloadResult(
                success=False,
                config_version="unknown",
                changes_applied=0,
                warnings=["Legacy method - use specific config operations instead"],
                error="Use specific configuration management endpoints instead"
            )

        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
            return ConfigReloadResult(
                success=False,
                config_version="unknown",
                changes_applied=0,
                warnings=[],
                error=str(e)
            )

    # Service interface methods required by Service base class
    async def is_healthy(self) -> bool:
        """Check if the runtime control service is healthy."""
        try:
            # Check if core components are available
            if not self.runtime:
                return False

            # Check processor status
            if self._processor_status == ProcessorStatus.ERROR:
                return False

            return True
        except Exception:
            return False

    def get_capabilities(self) -> 'ServiceCapabilities':
        """Get service capabilities."""
        from ciris_engine.schemas.services.core import ServiceCapabilities
        return ServiceCapabilities(
            service_name="RuntimeControlService",
            actions=[
                "single_step", "pause_processing", "resume_processing",
                "get_processor_queue_status", "shutdown_runtime",
                "load_adapter", "unload_adapter", "list_adapters", "get_adapter_info",
                "get_config", "update_config", "validate_config", "backup_config",
                "restore_config", "list_config_backups", "reload_config_profile",
                "get_runtime_status", "get_runtime_snapshot",
                "get_service_registry_info", "update_service_priority",
                "reset_circuit_breakers", "get_service_health_status"
            ],
            version="1.0.0",
            dependencies=[],
            metadata={
                "description": "Runtime control and management service",
                "features": ["processor_control", "adapter_management", "config_management", "health_monitoring"]
            }
        )

    def get_status(self) -> 'ServiceStatus':
        """Get current service status."""
        from ciris_engine.schemas.services.core import ServiceStatus
        return ServiceStatus(
            service_name="RuntimeControlService",
            service_type="CORE",
            is_healthy=self.runtime is not None,
            uptime_seconds=(self._now() - self._start_time).total_seconds() if hasattr(self, '_start_time') else 0.0,
            last_error=None,
            metrics={
                "events_count": float(len(self._events_history)),
                "adapters_loaded": float(len(self.adapter_manager.active_adapters) if self.adapter_manager and hasattr(self.adapter_manager, 'active_adapters') else 0)
            },
            last_health_check=self._now(),
            custom_metrics={}
        )

    async def start(self) -> None:
        """Start the runtime control service."""
        await self._initialize()
        logger.info("Runtime control service started")

    async def stop(self) -> None:
        """Stop the runtime control service."""
        logger.info("Runtime control service stopping")
        # Clean up any resources if needed
        self._events_history.clear()
