"""Runtime control service for processor and adapter management."""
import logging
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from ciris_engine.logic.services.graph.config_service import ConfigManagerService

from ciris_engine.protocols.services import RuntimeControlService as RuntimeControlServiceProtocol
from ciris_engine.logic.runtime.adapter_manager import RuntimeAdapterManager
from ciris_engine.logic.adapters.base import Service
# ConfigManagerService is injected via dependency injection to avoid circular imports
from enum import Enum

from ciris_engine.schemas.services.core.runtime import (
    ProcessorStatus, ProcessorQueueStatus, AdapterInfo, AdapterOperationResult,
    ConfigBackup, ServiceRegistryInfo, CircuitBreakerResetResult,
    ServiceHealthStatus, ServiceSelectionExplanation, RuntimeEvent,
    ConfigReloadResult, ProcessorControlResponse, AdapterOperationResponse,
    RuntimeStatusResponse, RuntimeStateSnapshot, ConfigOperationResponse,
    ConfigValidationResponse, ConfigBackupResponse, ConfigScope,
    ConfigValidationLevel, AdapterStatus
)
from ciris_engine.schemas.services.core.runtime_config import (
    AdapterConfig, ProcessorConfig, RuntimeConfig, ServiceInfo, ServiceHealthReport
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
        self._start_time = self._time_service.now()
        self._last_config_change: Optional[datetime] = None
        self._events_history: List[RuntimeEvent] = []
        
        # Kill switch configuration
        self._kill_switch_config = KillSwitchConfig()
        self._wa_public_keys = {}  # wa_id -> Ed25519PublicKey

    def _get_config_manager(self) -> "ConfigManagerService":
        """Get config manager with lazy initialization to avoid circular imports."""
        if self.config_manager is None:
            self.config_manager = ConfigManagerService()
        return self.config_manager

    async def _initialize(self) -> None:
        """Initialize the runtime control service."""
        try:
            await self._get_config_manager().initialize()
            logger.info("Runtime control service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize runtime control service: {e}")
            raise

    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        try:
            start_time = self._time_service.now()
            
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
                new_status=self._processor_status
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
            start_time = self._time_service.now()
            
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
                new_status=self._processor_status
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
            start_time = self._time_service.now()
            
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
                new_status=self._processor_status
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
            start_time = self._time_service.now()
            
            logger.critical(f"RUNTIME SHUTDOWN INITIATED: {reason}")
            
            # Record the shutdown event
            await self._record_event("processor_control", "shutdown", success=True, result={"reason": reason})
            
            # Request global shutdown through the shutdown service
            if hasattr(self.runtime, 'service_registry'):
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
                new_status=self._processor_status
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
        status = EmergencyShutdownStatus(
            command_received=self._time_service.now()
        )
        
        try:
            # Verify WA signature
            if not self._verify_wa_signature(command):
                status.command_verified = False
                status.verification_error = "Invalid WA signature"
                logger.error(f"Emergency shutdown rejected: Invalid signature from {command.wa_id}")
                return status
            
            status.command_verified = True
            status.shutdown_initiated = self._time_service.now()
            
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
            if hasattr(self.runtime, 'service_registry'):
                shutdown_service = self.runtime.service_registry.get_service('ShutdownService')
                if shutdown_service:
                    shutdown_service.request_shutdown(shutdown_reason)
                    status.shutdown_completed = self._time_service.now()
                    status.exit_code = 0
                    logger.info("Emergency shutdown delegated to ShutdownService")
                    return status
            
            # Fallback to direct shutdown
            await self.shutdown_runtime(shutdown_reason)
            status.shutdown_completed = self._time_service.now()
            status.exit_code = 0
            
            return status
            
        except Exception as e:
            logger.critical(f"Emergency shutdown failed: {e}")
            status.verification_error = str(e)
            status.shutdown_completed = self._time_service.now()
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
        
        if not self.adapter_manager:
            return AdapterOperationResponse(
                success=False,
                timestamp=self._time_service.now(),
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )
        
        result = await self.adapter_manager.load_adapter(adapter_type, adapter_id, config)
        
        return AdapterOperationResponse(
            success=result.get("success", False),
            adapter_id=result.get("adapter_id", adapter_id),
            adapter_type=adapter_type,
            timestamp=self._time_service.now(),
            status=AdapterStatus.RUNNING if result.get("success") else AdapterStatus.ERROR,
            message=result.get("message"),
            error=result.get("error")
        )

    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterOperationResponse:
        """Unload an adapter instance."""
        # AdapterStatus is already imported at module level
        
        if not self.adapter_manager:
            return AdapterOperationResponse(
                success=False,
                timestamp=self._time_service.now(),
                adapter_id=adapter_id,
                adapter_type="unknown",
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )
        
        # Call adapter manager (note: it doesn't use force parameter)  
        result = await self.adapter_manager.unload_adapter(adapter_id)
        
        # Convert dict response to AdapterOperationResponse
        return AdapterOperationResponse(
            success=result.get("success", False),
            adapter_id=result.get("adapter_id", adapter_id),
            adapter_type=result.get("adapter_type", "unknown"),
            timestamp=self._time_service.now(),
            status=AdapterStatus.STOPPED if result.get("success") else AdapterStatus.ERROR,
            message=result.get("message"),
            error=result.get("error")
        )

    async def list_adapters(self) -> List[AdapterInfo]:
        """List all loaded adapters."""
        if not self.adapter_manager:
            return []
        
        adapters_raw = await self.adapter_manager.list_adapters()
        adapters_list = []
        
        for adapter_dict in adapters_raw:
            # Map the status string to AdapterStatus enum
            status_str = adapter_dict.get("status", "unknown")
            try:
                status = AdapterStatus(status_str)
            except ValueError:
                status = AdapterStatus.ERROR
                
            adapters_list.append(AdapterInfo(
                adapter_id=adapter_dict.get("adapter_id", ""),
                adapter_type=adapter_dict.get("adapter_type", ""),
                status=status,
                started_at=adapter_dict.get("loaded_at", self._time_service.now()),
                messages_processed=adapter_dict.get("metrics", {}).get("messages_processed", 0),
                error_count=adapter_dict.get("metrics", {}).get("errors_count", 0),
                last_error=adapter_dict.get("metrics", {}).get("last_error")
            ))
        
        return adapters_list

    async def get_adapter_info(self, adapter_id: str) -> Optional[AdapterInfo]:
        """Get detailed information about a specific adapter."""
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
            started_at=info.get("loaded_at", self._time_service.now()),
            messages_processed=info.get("metrics", {}).get("messages_processed", 0),
            error_count=info.get("metrics", {}).get("errors_count", 0),
            last_error=info.get("metrics", {}).get("last_error")
        )

    # Configuration Management Methods
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> RuntimeStateSnapshot:
        """Get configuration value(s)."""
        try:
            return await self._get_config_manager().get_config_value(path, include_sensitive)
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return {"error": str(e)}

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
            
            result = await self._get_config_manager().update_config_value(
                path, value, config_scope, config_validation, reason
            )
            if result.success:
                self._last_config_change = result.timestamp
            return result
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="update_config",
                timestamp=self._time_service.now(),
                path=path,
                error=str(e)
            )

    async def validate_config(
        self,
        config_data: Dict[str, object],
        config_path: Optional[str] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        try:
            return await self._get_config_manager().validate_config(config_data, config_path)
        except Exception as e:
            logger.error(f"Failed to validate config: {e}")
            return ConfigValidationResponse(
                valid=False,
                errors=[str(e)]
            )

    async def backup_config(
        self,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a configuration backup."""
        try:
            return await self._get_config_manager().backup_config(
                include_profiles=True,
                backup_name=backup_name
            )
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="backup_config",
                backup_name=backup_name or "unknown",
                timestamp=self._time_service.now(),
                error=str(e)
            )

    async def restore_config(
        self,
        backup_name: str
    ) -> ConfigOperationResponse:
        """Restore configuration from backup."""
        try:
            # For now, restore all components from the backup
            result = await self._get_config_manager().restore_config(
                backup_name,
                restore_profiles=True,
                restore_env_vars=True,
                restart_required=False
            )
            
            # Convert to ConfigOperationResponse
            return ConfigOperationResponse(
                success=result.get("success", False),
                path="config",
                old_value=None,
                new_value=backup_name,
                timestamp=self._time_service.now(),
                message=result.get("message", "Configuration restored from backup")
            )
        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return ConfigOperationResponse(
                success=False,
                path="config",
                old_value=None,
                new_value=backup_name,
                timestamp=self._time_service.now(),
                error=str(e)
            )

    async def list_config_backups(self) -> List[ConfigBackup]:
        """List available configuration backups."""
        try:
            return await self._get_config_manager().list_config_backups()
        except Exception as e:
            logger.error(f"Failed to list config backups: {e}")
            return []

    async def get_runtime_status(self) -> RuntimeStatusResponse:
        """Get current runtime status."""
        try:
            current_time = self._time_service.now()
            uptime = (current_time - self._start_time).total_seconds()
            
            # Get adapter information
            adapters = []
            if self.adapter_manager:
                adapters = await self.adapter_manager.list_adapters()
            active_adapters = [a["adapter_id"] for a in adapters if a.get("status") == "active" or a.get("is_running") is True]
            loaded_adapters = [a["adapter_id"] for a in adapters]
            
            # Agent identity is now stored in graph, not profiles
            current_profile = "identity-based"
            
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
            current_time = self._time_service.now()
            uptime = (current_time - self._start_time).total_seconds()
            
            adapters_data = []
            if self.adapter_manager:
                adapters_data = await self.adapter_manager.list_adapters()
            
            config_data = await self._get_config_manager().get_config_value()
            
            # Profiles are no longer used after initial agent creation
            profile_names: List[str] = []
            active_profile = "identity-based"
            
            return RuntimeStateSnapshot(
                timestamp=current_time,
                processor_status=self._processor_status,
                adapters=[],  # Would convert adapters_data to AdapterInfo objects
                configuration=config_data,
                active_profile=active_profile,
                loaded_profiles=profile_names,
                uptime_seconds=uptime,
                memory_usage_mb=0.0,  # Would get from system metrics
                system_health="healthy"  # Would get from health check
            )
            
        except Exception as e:
            logger.error(f"Failed to get runtime snapshot: {e}")
            raise

    async def _get_service_registry_info(self, handler: Optional[str] = None, service_type: Optional[str] = None) -> ServiceRegistryInfo:
        """Get information about registered services in the service registry."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return {"error": "Service registry not available"}
            
            info = self.runtime.service_registry.get_provider_info(handler, service_type)
            # Ensure we always return a dict
            if isinstance(info, dict):
                return info
            else:
                return {"data": info}
        except Exception as e:
            logger.error(f"Failed to get service registry info: {e}")
            return {"error": str(e)}

    async def _update_service_priority(
        self, 
        provider_name: str, 
        new_priority: str, 
        new_priority_group: Optional[int] = None,
        new_strategy: Optional[str] = None
    ) -> ServiceHealthReport:
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
            
            # Check handler-specific services
            for handler, services in registry._providers.items():
                for service_type, providers in services.items():
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
                                "handler": handler,
                                "service_type": service_type,
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
                if provider_found:
                    break
            
            # If not found in handler-specific, check global services
            if not provider_found:
                for service_type, providers in registry._global_services.items():
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
                                "handler": "global",
                                "service_type": service_type,
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
                "timestamp": self._time_service.now().isoformat()
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

    async def _reset_circuit_breakers(self, service_type: Optional[str] = None) -> CircuitBreakerResetResult:
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
                "timestamp": self._time_service.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to reset circuit breakers: {e}")
            await self._record_event("service_management", "reset_circuit_breakers", False, error=str(e))
            return {"success": False, "error": str(e)}

    async def get_service_health_status(self) -> ServiceHealthStatus:
        """Get health status of all registered services."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return ServiceHealthStatus(
                    overall_health="critical",
                    healthy_services=[],
                    unhealthy_services=["error: Service registry not available"],
                    service_details={},
                    recommendations=["Check runtime initialization"]
                )
                
            registry_info = self.runtime.service_registry.get_provider_info()
            health_status = ServiceHealthReport(
                overall_health="healthy",
                healthy_services=0,
                unhealthy_services=0,
                services={},
                system_load=0.0,
                memory_percent=0.0
            )
            
            for handler, services in registry_info.get("handlers", {}).items():
                for service_type, providers in services.items():
                    for provider in providers:
                        service_key = f"{handler}.{service_type}.{provider['name']}"
                        cb_state = provider.get('circuit_breaker_state', 'closed')
                        is_healthy = cb_state == 'closed'
                        
                        health_status["services"][service_key] = {
                            "healthy": is_healthy,
                            "circuit_breaker_state": cb_state,
                            "priority": provider['priority'],
                            "priority_group": provider['priority_group'],
                            "strategy": provider['strategy']
                        }
                        health_status["total_services"] += 1
                        if is_healthy:
                            health_status["healthy_services"] += 1
                        else:
                            health_status["unhealthy_services"] += 1
            
            for service_type, providers in registry_info.get("global_services", {}).items():
                for provider in providers:
                    service_key = f"global.{service_type}.{provider['name']}"
                    cb_state = provider.get('circuit_breaker_state', 'closed')
                    is_healthy = cb_state == 'closed'
                    
                    health_status["services"][service_key] = {
                        "healthy": is_healthy,
                        "circuit_breaker_state": cb_state,
                        "priority": provider['priority'],
                        "priority_group": provider['priority_group'],
                        "strategy": provider['strategy']
                    }
                    health_status["total_services"] += 1
                    if is_healthy:
                        health_status["healthy_services"] += 1
                    else:
                        health_status["unhealthy_services"] += 1
            
            if health_status["unhealthy_services"] > 0:
                if health_status["unhealthy_services"] > health_status["healthy_services"]:
                    health_status["overall_health"] = "unhealthy"
                else:
                    health_status["overall_health"] = "degraded"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to get service health status: {e}")
            return {"error": str(e)}

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
            import uuid
            event = RuntimeEvent(
                event_type=f"{category}:{action}",
                timestamp=self._time_service.now(),
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
            
            return {
                "success": False,
                "error": "Use specific configuration management endpoints instead",
                "timestamp": self._time_service.now().isoformat(),
                "suggestion": "Use /v1/runtime/config/reload-profile or /v1/runtime/config/update endpoints"
            }
            
        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": self._time_service.now().isoformat()
            }
    
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
            is_healthy=self._processor is not None,
            uptime_seconds=0.0,  # Would need to track start time
            last_error=None,
            metrics={
                "events_count": float(len(self._events_history)),
                "adapters_loaded": float(len(self._adapter_manager.active_adapters) if self._adapter_manager else 0)
            },
            last_health_check=self._time_service.now()
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
