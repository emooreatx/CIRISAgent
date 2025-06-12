"""
Runtime Control Service

Comprehensive runtime control service that manages processor lifecycle,
adapter management, and configuration operations. This centralizes all
runtime control operations in a single module following the established
architecture patterns.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from ciris_engine.protocols.runtime_control import RuntimeControlInterface
from ciris_engine.runtime.adapter_manager import RuntimeAdapterManager
from ciris_engine.runtime.config_manager_service import ConfigManagerService
from ciris_engine.schemas.runtime_control_schemas import (
    ProcessorStatus, ProcessorControlResponse, AdapterOperationResponse,
    RuntimeStatusResponse, RuntimeStateSnapshot, ConfigOperationResponse,
    ConfigValidationResponse, AgentProfileResponse, EnvVarResponse,
    ConfigBackupResponse, ConfigScope, ConfigValidationLevel
)


logger = logging.getLogger(__name__)


class RuntimeControlService(RuntimeControlInterface):
    """
    Comprehensive runtime control service providing processor management,
    adapter lifecycle operations, and configuration updates.
    """

    def __init__(self, telemetry_collector=None, adapter_manager: Optional[RuntimeAdapterManager] = None, config_manager: Optional[ConfigManagerService] = None):
        """
        Initialize the runtime control service.
        
        Args:
            runtime: CIRISRuntime instance for system access
        """
        self.telemetry_collector = telemetry_collector
        self.adapter_manager = adapter_manager or RuntimeAdapterManager()
        self.config_manager = config_manager or ConfigManagerService()
        self._processor_status = ProcessorStatus.RUNNING
        self._start_time = datetime.now(timezone.utc)
        self._last_config_change: Optional[datetime] = None
        self._events_history: List[Dict[str, Any]] = []

    async def initialize(self) -> None:
        """Initialize the runtime control service."""
        try:
            await self.adapter_manager.initialize()
            await self.config_manager.initialize()
            logger.info("Runtime control service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize runtime control service: {e}")
            raise

    # Processor Control Methods

    async def start_processing(self, num_rounds: Optional[int] = None) -> ProcessorControlResult:
        """Start the processor with optional round limit"""
        async with self._operation_lock:
            try:
                start_time = datetime.now(timezone.utc)
                
                if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                    processor = self.runtime.agent_processor
                    
                    # Check if processor is already running
                    is_already_running = (
                        hasattr(processor, '_processing_task') and 
                        processor._processing_task is not None and 
                        not processor._processing_task.done()
                    )
                    
                    if is_already_running:
                        return ProcessorControlResult(
                            success=False,
                            operation="start",
                            status="already_running",
                            details={"message": "Processor is already running"}
                        )
                    
                    # Start the processor
                    await processor.start_processing(num_rounds)
                    
                    # Record the event
                    await self._record_event("processor_start", "start", success=True, details={
                        "num_rounds": num_rounds,
                        "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    })
                    
                    return ProcessorControlResult(
                        success=True,
                        operation="start",
                        status="started",
                        details={
                            "num_rounds": num_rounds,
                            "started_at": start_time.isoformat()
                        }
                    )
                else:
                    return ProcessorControlResult(
                        success=False,
                        operation="start",
                        status="processor_not_available",
                        details={"error": "Agent processor not found in runtime"}
                    )
                    
            except Exception as e:
                logger.error(f"Failed to start processing: {e}", exc_info=True)
                await self._record_event("processor_start", "start", success=False, error=str(e))
                return ProcessorControlResult(
                    success=False,
                    operation="start",
                    status="error",
                    details={"error": str(e)}
                )

    async def stop_processing(self) -> ProcessorControlResult:
        """Stop the processor gracefully"""
        async with self._operation_lock:
            try:
                start_time = datetime.now(timezone.utc)
                
                if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                    processor = self.runtime.agent_processor
                    
                    # Check if processor is running
                    is_running = (
                        hasattr(processor, '_processing_task') and 
                        processor._processing_task is not None and 
                        not processor._processing_task.done()
                    )
                    
                    if not is_running:
                        return ProcessorControlResult(
                            success=False,
                            operation="stop",
                            status="not_running",
                            details={"message": "Processor is not currently running"}
                        )
                    
                    # Stop the processor
                    await processor.stop_processing()
                    
                    # Record the event
                    await self._record_event("processor_stop", "stop", success=True, details={
                        "execution_time_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                    })
                    
                    return ProcessorControlResult(
                        success=True,
                        operation="stop",
                        status="stopped",
                        details={
                            "stopped_at": start_time.isoformat()
                        }
                    )
                else:
                    return ProcessorControlResult(
                        success=False,
                        operation="stop",
                        status="processor_not_available",
                        details={"error": "Agent processor not found in runtime"}
                    )
                    
            except Exception as e:
                logger.error(f"Failed to stop processing: {e}", exc_info=True)
                await self._record_event("processor_stop", "stop", success=False, error=str(e))
                return ProcessorControlResult(
                    success=False,
                    operation="stop",
                    status="error",
                    details={"error": str(e)}
                )

    async def pause_processing(self) -> ProcessorControlResult:
        """Pause the processor temporarily"""
        # For now, implement as stop (pause/resume can be enhanced later)
        result = await self.stop_processing()
        result.operation = "pause"
        result.status = result.status.replace("stopped", "paused")
        return result

    async def resume_processing(self) -> ProcessorControlResult:
        """Resume a paused processor"""
        # For now, implement as start (pause/resume can be enhanced later)
        result = await self.start_processing()
        result.operation = "resume"
        result.status = result.status.replace("started", "resumed")
        return result

    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        try:
            start_time = datetime.now(timezone.utc)
            
            if not self.telemetry_collector:
                return ProcessorControlResponse(
                    success=False,
                    action="single_step",
                    timestamp=start_time,
                    error="Telemetry collector not available"
                )
            
            result = await self.telemetry_collector.single_step()
            await self._record_event("processor_control", "single_step", success=True, result=result)
            
            return ProcessorControlResponse(
                success=True,
                action="single_step",
                timestamp=start_time,
                result=result
            )
            
        except Exception as e:
            logger.error(f"Failed to execute single step: {e}", exc_info=True)
            await self._record_event("processor_control", "single_step", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                action="single_step",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Adapter Management Methods

    async def load_adapter(self, request: AdapterLoadRequest) -> AdapterLoadResult:
        """Load and optionally start a new adapter"""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Generate adapter ID if not provided
            adapter_id = f"{request.adapter_type}_{uuid.uuid4().hex[:8]}"
            
            # Load the adapter using the adapter manager
            result = await self.adapter_manager.load_adapter(
                mode=request.adapter_type,
                adapter_id=adapter_id,
                config_params=request.adapter_config
            )
            
            if result["success"]:
                # Record success event
                await self._record_event("adapter_load", "load", target=adapter_id, success=True, details={
                    "adapter_type": request.adapter_type,
                    "services_registered": result.get("services_registered", 0),
                    "auto_start": request.auto_start
                })
                
                return AdapterLoadResult(
                    success=True,
                    adapter_id=adapter_id,
                    adapter_type=request.adapter_type,
                    status="loaded" if request.auto_start else "loaded_not_started",
                    services_registered=result.get("services_registered", [])
                )
            else:
                # Record failure event
                await self._record_event("adapter_load", "load", target=adapter_id, success=False, error=result.get("error"))
                
                return AdapterLoadResult(
                    success=False,
                    adapter_id=adapter_id,
                    adapter_type=request.adapter_type,
                    status="error",
                    error_message=result.get("error")
                )
                
        except Exception as e:
            logger.error(f"Failed to load adapter: {e}", exc_info=True)
            await self._record_event("adapter_load", "load", success=False, error=str(e))
            return AdapterLoadResult(
                success=False,
                adapter_id="unknown",
                adapter_type=request.adapter_type,
                status="error",
                error_message=str(e)
            )

    async def unload_adapter(self, adapter_id: str) -> AdapterUnloadResult:
        """Stop and unload an adapter"""
        try:
            result = await self.adapter_manager.unload_adapter(adapter_id)
            
            if result["success"]:
                await self._record_event("adapter_unload", "unload", target=adapter_id, success=True, details={
                    "services_unregistered": result.get("services_unregistered", 0)
                })
                
                return AdapterUnloadResult(
                    success=True,
                    adapter_id=adapter_id,
                    status="unloaded",
                    services_unregistered=result.get("services_unregistered", [])
                )
            else:
                await self._record_event("adapter_unload", "unload", target=adapter_id, success=False, error=result.get("error"))
                
                return AdapterUnloadResult(
                    success=False,
                    adapter_id=adapter_id,
                    status="error",
                    error_message=result.get("error")
                )
                
        except Exception as e:
            logger.error(f"Failed to unload adapter {adapter_id}: {e}", exc_info=True)
            await self._record_event("adapter_unload", "unload", target=adapter_id, success=False, error=str(e))
            return AdapterUnloadResult(
                success=False,
                adapter_id=adapter_id,
                status="error",
                error_message=str(e)
            )

    async def start_adapter(self, adapter_id: str) -> AdapterLoadResult:
        """Start a loaded but stopped adapter"""
        # For now, this is handled by the load_adapter process
        # Future enhancement could separate loading from starting
        return AdapterLoadResult(
            success=False,
            adapter_id=adapter_id,
            adapter_type="unknown",
            status="not_implemented",
            error_message="Separate start/stop not yet implemented"
        )

    async def stop_adapter(self, adapter_id: str) -> AdapterUnloadResult:
        """Stop a running adapter without unloading it"""
        # For now, this is handled by the unload_adapter process
        # Future enhancement could separate stopping from unloading
        return AdapterUnloadResult(
            success=False,
            adapter_id=adapter_id,
            status="not_implemented",
            error_message="Separate start/stop not yet implemented"
        )

    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapters and their status"""
        try:
            return await self.adapter_manager.list_adapters()
        except Exception as e:
            logger.error(f"Failed to list adapters: {e}", exc_info=True)
            return []

    # Configuration Management Methods

    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get configuration value(s)."""
        try:
            return await self.config_manager.get_config_value(path, include_sensitive)
        except Exception as e:
            logger.error(f"Failed to get config: {e}")
            return {"error": str(e)}

    async def update_config(
        self,
        path: str,
        value: Any,
        scope: ConfigScope = ConfigScope.RUNTIME,
        validation_level: ConfigValidationLevel = ConfigValidationLevel.STRICT,
        reason: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update a configuration value."""
        try:
            result = await self.config_manager.update_config_value(
                path, value, scope, validation_level, reason
            )
            if result.success:
                self._last_config_change = result.timestamp
            return result
        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="update_config",
                timestamp=datetime.now(timezone.utc),
                path=path,
                error=str(e)
            )

    async def validate_config(
        self,
        config_data: Dict[str, Any],
        config_path: Optional[str] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        try:
            return await self.config_manager.validate_config(config_data, config_path)
        except Exception as e:
            logger.error(f"Failed to validate config: {e}")
            return ConfigValidationResponse(
                valid=False,
                errors=[str(e)]
            )

    async def reload_profile(
        self,
        profile_name: str,
        config_path: Optional[str] = None,
        scope: ConfigScope = ConfigScope.SESSION
    ) -> ConfigOperationResponse:
        """Reload an agent profile."""
        try:
            result = await self.config_manager.reload_profile(profile_name, config_path, scope)
            if result.success:
                self._last_config_change = result.timestamp
                # Notify adapter manager of profile change
                await self.adapter_manager.on_profile_changed(profile_name)
            return result
        except Exception as e:
            logger.error(f"Failed to reload profile: {e}")
            return ConfigOperationResponse(
                success=False,
                operation="reload_profile",
                timestamp=datetime.now(timezone.utc),
                path=f"profile:{profile_name}",
                error=str(e)
            )

    async def list_profiles(self) -> List[Dict[str, Any]]:
        """List all available agent profiles."""
        try:
            profiles = await self.config_manager.list_profiles()
            return [profile.model_dump() for profile in profiles]
        except Exception as e:
            logger.error(f"Failed to list profiles: {e}")
            return []

    async def create_profile(
        self,
        name: str,
        config: Dict[str, Any],
        description: Optional[str] = None,
        base_profile: Optional[str] = None,
        save_to_file: bool = True
    ) -> AgentProfileResponse:
        """Create a new agent profile."""
        try:
            return await self.config_manager.create_profile(
                name, config, description, base_profile, save_to_file
            )
        except Exception as e:
            logger.error(f"Failed to create profile: {e}")
            return AgentProfileResponse(
                success=False,
                profile_name=name,
                operation="create_profile",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Environment Variable Management
    async def set_env_var(
        self,
        name: str,
        value: str,
        persist: bool = False,
        reload_config: bool = True
    ) -> EnvVarResponse:
        """Set an environment variable."""
        try:
            result = await self.config_manager.set_env_var(name, value, persist, reload_config)
            if result.success and reload_config:
                self._last_config_change = result.timestamp
            return result
        except Exception as e:
            logger.error(f"Failed to set env var: {e}")
            return EnvVarResponse(
                success=False,
                operation="set_env_var",
                variable_name=name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def delete_env_var(
        self,
        name: str,
        persist: bool = False,
        reload_config: bool = True
    ) -> EnvVarResponse:
        """Delete an environment variable."""
        try:
            result = await self.config_manager.delete_env_var(name, persist, reload_config)
            if result.success and reload_config:
                self._last_config_change = result.timestamp
            return result
        except Exception as e:
            logger.error(f"Failed to delete env var: {e}")
            return EnvVarResponse(
                success=False,
                operation="delete_env_var",
                variable_name=name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Backup and Restore
    async def backup_config(
        self,
        include_profiles: bool = True,
        include_env_vars: bool = False,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a configuration backup."""
        try:
            return await self.config_manager.backup_config(
                include_profiles, include_env_vars, backup_name
            )
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="backup_config",
                backup_name=backup_name or "unknown",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Status and Monitoring
    async def get_runtime_status(self) -> RuntimeStatusResponse:
        """Get current runtime status."""
        try:
            current_time = datetime.now(timezone.utc)
            uptime = (current_time - self._start_time).total_seconds()
            
            # Get adapter information
            adapters = await self.adapter_manager.list_adapters()
            active_adapters = [a["adapter_id"] for a in adapters if a.get("status") == "active"]
            loaded_adapters = [a["adapter_id"] for a in adapters]
            
            # Get current profile (placeholder - would need integration with config)
            current_profile = "default"  # Would get from actual config
            
            return RuntimeStatusResponse(
                processor_status=self._processor_status,
                active_adapters=active_adapters,
                loaded_adapters=loaded_adapters,
                current_profile=current_profile,
                config_scope=ConfigScope.RUNTIME,  # Would get from actual config
                uptime_seconds=uptime,
                last_config_change=self._last_config_change
            )
            
        except Exception as e:
            logger.error(f"Failed to get runtime status: {e}")
            return RuntimeStatusResponse(
                processor_status=ProcessorStatus.ERROR,
                active_adapters=[],
                loaded_adapters=[],
                current_profile="unknown",
                config_scope=ConfigScope.RUNTIME,
                uptime_seconds=0.0
            )

    async def get_runtime_snapshot(self) -> RuntimeStateSnapshot:
        """Get complete runtime state snapshot."""
        try:
            current_time = datetime.now(timezone.utc)
            uptime = (current_time - self._start_time).total_seconds()
            
            # Get detailed adapter information
            adapters_data = await self.adapter_manager.list_adapters()
            
            # Get configuration
            config_data = await self.config_manager.get_config_value()
            
            # Get profiles
            profiles = await self.config_manager.list_profiles()
            profile_names = [p.name for p in profiles]
            active_profile = next((p.name for p in profiles if p.is_active), "default")
            
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

    # Helper Methods
    async def _record_event(
        self,
        category: str,
        action: str,
        success: bool,
        result: Any = None,
        error: Optional[str] = None
    ) -> None:
        """Record an event in the history."""
        try:
            event = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "action": action,
                "success": success,
                "result": result,
                "error": error
            }
            
            self._events_history.append(event)
            
            # Limit history size
            if len(self._events_history) > 1000:
                self._events_history = self._events_history[-1000:]
                
        except Exception as e:
            logger.error(f"Failed to record event: {e}")

    def get_events_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events history."""
        return self._events_history[-limit:]

    # Legacy method to maintain compatibility
    async def reload_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Reload system configuration."""
        try:
            # For now, return not fully implemented
            # This would require more sophisticated config reloading
            await self._record_event("config_reload", "reload", success=False, error="Legacy method - use specific config operations instead")
            
            return {
                "success": False,
                "error": "Use specific configuration management endpoints instead",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "suggestion": "Use /v1/runtime/config/reload-profile or /v1/runtime/config/update endpoints"
            }
            
        except Exception as e:
            logger.error(f"Failed to reload config: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
