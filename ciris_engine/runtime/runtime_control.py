# filepath: /home/emoore/CIRISAgent/ciris_engine/runtime/runtime_control.py
"""Runtime control service for processor and adapter management."""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from ciris_engine.protocols.runtime_control import RuntimeControlInterface
from ciris_engine.runtime.adapter_manager import RuntimeAdapterManager
# ConfigManagerService is injected via dependency injection to avoid circular imports
from ciris_engine.schemas.runtime_control_schemas import (
    ProcessorStatus, ProcessorControlResponse, AdapterOperationResponse,
    RuntimeStatusResponse, RuntimeStateSnapshot, ConfigOperationResponse,
    ConfigValidationResponse, AgentProfileResponse,
    ConfigBackupResponse, ConfigScope, ConfigValidationLevel
)

logger = logging.getLogger(__name__)


class RuntimeControlService(RuntimeControlInterface):
    """Service for runtime control of processor, adapters, and configuration."""

    def __init__(
        self,
        runtime=None,
        telemetry_collector=None,
        adapter_manager: Optional[RuntimeAdapterManager] = None,
        config_manager: Optional[Any] = None
    ):
        self.runtime = runtime
        self.telemetry_collector = telemetry_collector
        self.adapter_manager = adapter_manager
        if not self.adapter_manager and runtime:
            self.adapter_manager = RuntimeAdapterManager(runtime)
        self.config_manager = config_manager
        self._processor_status = ProcessorStatus.RUNNING
        self._start_time = datetime.now(timezone.utc)
        self._last_config_change: Optional[datetime] = None
        self._events_history: List[Dict[str, Any]] = []

    def _get_config_manager(self):
        """Get config manager with lazy initialization to avoid circular imports."""
        if self.config_manager is None:
            from ciris_engine.services.config_manager_service import ConfigManagerService
            self.config_manager = ConfigManagerService()
        return self.config_manager

    async def initialize(self) -> None:
        """Initialize the runtime control service."""
        try:
            # RuntimeAdapterManager doesn't have an initialize method
            # Only initialize config_manager
            await self._get_config_manager().initialize()
            logger.info("Runtime control service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize runtime control service: {e}")
            raise

    # Processor Control Methods
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

    async def pause_processing(self) -> ProcessorControlResponse:
        """Pause the processor."""
        try:
            start_time = datetime.now(timezone.utc)
            
            if not self.telemetry_collector:
                return ProcessorControlResponse(
                    success=False,
                    action="pause",
                    timestamp=start_time,
                    error="Telemetry collector not available"
                )
            
            await self.telemetry_collector.pause_processing()
            self._processor_status = ProcessorStatus.PAUSED
            await self._record_event("processor_control", "pause", success=True)
            
            return ProcessorControlResponse(
                success=True,
                action="pause",
                timestamp=start_time,
                result={"status": "paused"}
            )
            
        except Exception as e:
            logger.error(f"Failed to pause processing: {e}", exc_info=True)
            await self._record_event("processor_control", "pause", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                action="pause",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def resume_processing(self) -> ProcessorControlResponse:
        """Resume the processor."""
        try:
            start_time = datetime.now(timezone.utc)
            
            if not self.telemetry_collector:
                return ProcessorControlResponse(
                    success=False,
                    action="resume",
                    timestamp=start_time,
                    error="Telemetry collector not available"
                )
            
            await self.telemetry_collector.resume_processing()
            self._processor_status = ProcessorStatus.RUNNING
            await self._record_event("processor_control", "resume", success=True)
            
            return ProcessorControlResponse(
                success=True,
                action="resume",
                timestamp=start_time,
                result={"status": "running"}
            )
            
        except Exception as e:
            logger.error(f"Failed to resume processing: {e}", exc_info=True)
            await self._record_event("processor_control", "resume", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                action="resume",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def get_processor_queue_status(self) -> Dict[str, Any]:
        """Get processor queue status."""
        try:
            if not self.telemetry_collector:
                return {"error": "Telemetry collector not available"}
            
            status = await self.telemetry_collector.get_processing_queue_status()
            await self._record_event("processor_query", "queue_status", success=True)
            return status
            
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}", exc_info=True)
            await self._record_event("processor_query", "queue_status", success=False, error=str(e))
            return {"error": str(e)}

    async def shutdown_runtime(self, reason: str = "Runtime shutdown requested") -> ProcessorControlResponse:
        """Shutdown the entire runtime system."""
        try:
            start_time = datetime.now(timezone.utc)
            
            logger.critical(f"RUNTIME SHUTDOWN INITIATED: {reason}")
            
            # Record the shutdown event
            await self._record_event("processor_control", "shutdown", success=True, result={"reason": reason})
            
            # Request global shutdown through the shutdown manager
            from ciris_engine.utils.shutdown_manager import request_global_shutdown
            request_global_shutdown(f"Runtime control: {reason}")
            
            # Set processor status to stopped
            self._processor_status = ProcessorStatus.STOPPED
            
            return ProcessorControlResponse(
                success=True,
                action="shutdown",
                timestamp=start_time,
                result={"status": "shutdown_initiated", "reason": reason}
            )
            
        except Exception as e:
            logger.error(f"Failed to initiate shutdown: {e}", exc_info=True)
            await self._record_event("processor_control", "shutdown", success=False, error=str(e))
            return ProcessorControlResponse(
                success=False,
                action="shutdown",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    # Adapter Management Methods
    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: str,
        config: Dict[str, Any],
        auto_start: bool = True
    ) -> AdapterOperationResponse:
        """Load a new adapter instance."""
        if not self.adapter_manager:
            from ciris_engine.schemas.runtime_control_schemas import AdapterStatus
            return AdapterOperationResponse(
                success=False,
                timestamp=datetime.now(timezone.utc),
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )
        
        # Call adapter manager (note: it doesn't use auto_start parameter)
        result = await self.adapter_manager.load_adapter(adapter_type, adapter_id, config)
        
        # Convert dict response to AdapterOperationResponse
        from ciris_engine.schemas.runtime_control_schemas import AdapterStatus
        return AdapterOperationResponse(
            success=result.get("success", False),
            adapter_id=result.get("adapter_id", adapter_id),
            adapter_type=adapter_type,
            timestamp=datetime.now(timezone.utc),
            status=AdapterStatus.ACTIVE if result.get("success") else AdapterStatus.ERROR,
            message=result.get("message"),
            error=result.get("error")
        )

    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterOperationResponse:
        """Unload an adapter instance."""
        if not self.adapter_manager:
            from ciris_engine.schemas.runtime_control_schemas import AdapterStatus
            return AdapterOperationResponse(
                success=False,
                timestamp=datetime.now(timezone.utc),
                adapter_id=adapter_id,
                adapter_type="unknown",
                status=AdapterStatus.ERROR,
                error="Adapter manager not available"
            )
        
        # Call adapter manager (note: it doesn't use force parameter)  
        result = await self.adapter_manager.unload_adapter(adapter_id)
        
        # Convert dict response to AdapterOperationResponse
        from ciris_engine.schemas.runtime_control_schemas import AdapterStatus
        return AdapterOperationResponse(
            success=result.get("success", False),
            adapter_id=result.get("adapter_id", adapter_id),
            adapter_type=result.get("mode", "unknown"),
            timestamp=datetime.now(timezone.utc),
            status=AdapterStatus.INACTIVE if result.get("success") else AdapterStatus.ERROR,
            message=result.get("message"),
            error=result.get("error")
        )

    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapters."""
        if not self.adapter_manager:
            return []
        return await self.adapter_manager.list_adapters()

    async def get_adapter_info(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific adapter."""
        if not self.adapter_manager:
            return {"error": "Adapter manager not available"}
        return await self.adapter_manager.get_adapter_info(adapter_id)

    # Configuration Management Methods
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get configuration value(s)."""
        try:
            return await self._get_config_manager().get_config_value(path, include_sensitive)
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
            result = await self._get_config_manager().update_config_value(
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
            return await self._get_config_manager().validate_config(config_data, config_path)
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
            result = await self._get_config_manager().reload_profile(profile_name, config_path, scope)
            if result.success:
                self._last_config_change = result.timestamp
                # Notify adapter manager of profile change if available
                if self.adapter_manager and hasattr(self.adapter_manager, 'on_profile_changed'):
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
            profiles = await self._get_config_manager().list_profiles()
            return [profile.model_dump() for profile in profiles]
        except Exception as e:
            logger.error(f"Failed to list profiles: {e}")
            return []

    # Alias for API compatibility
    async def list_agent_profiles(self) -> List[Dict[str, Any]]:
        """List all available agent profiles (API alias)."""
        return await self.list_profiles()

    async def load_agent_profile(self, reload_request) -> ConfigOperationResponse:
        """Load an agent profile (API method)."""
        return await self.reload_profile(
            reload_request.profile_name,
            reload_request.config_path,
            reload_request.scope
        )

    async def get_agent_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent profile."""
        try:
            profiles = await self._get_config_manager().list_profiles()
            for profile in profiles:
                if profile.name == profile_name:
                    return profile.model_dump()
            return None
        except Exception as e:
            logger.error(f"Failed to get profile {profile_name}: {e}")
            return None

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
            return await self._get_config_manager().create_profile(
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

    # Backup and Restore
    async def backup_config(
        self,
        backup_request
    ) -> ConfigBackupResponse:
        """Create a configuration backup (API method with request object)."""
        try:
            return await self._get_config_manager().backup_config(
                backup_request.include_profiles, 
                backup_request.backup_name
            )
        except Exception as e:
            logger.error(f"Failed to backup config: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="backup_config",
                backup_name=backup_request.backup_name or "unknown",
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def backup_config_direct(
        self,
        include_profiles: bool = True,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a configuration backup (direct method)."""
        try:
            return await self._get_config_manager().backup_config(
                include_profiles, backup_name
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

    async def restore_config(
        self,
        restore_request
    ) -> ConfigBackupResponse:
        """Restore configuration from backup."""
        try:
            return await self._get_config_manager().restore_config(
                restore_request.backup_name,
                restore_request.restore_profiles,
                restore_request.restore_env_vars,
                restore_request.restart_required
            )
        except Exception as e:
            logger.error(f"Failed to restore config: {e}")
            return ConfigBackupResponse(
                success=False,
                operation="restore_config",
                backup_name=restore_request.backup_name,
                timestamp=datetime.now(timezone.utc),
                error=str(e)
            )

    async def list_config_backups(self) -> List[Dict[str, Any]]:
        """List available configuration backups."""
        try:
            return await self._get_config_manager().list_config_backups()
        except Exception as e:
            logger.error(f"Failed to list config backups: {e}")
            return []

    # Status and Monitoring
    async def get_runtime_status(self) -> RuntimeStatusResponse:
        """Get current runtime status."""
        try:
            current_time = datetime.now(timezone.utc)
            uptime = (current_time - self._start_time).total_seconds()
            
            # Get adapter information
            adapters = []
            if self.adapter_manager:
                adapters = await self.adapter_manager.list_adapters()
            active_adapters = [a["adapter_id"] for a in adapters if a.get("status") == "active" or a.get("is_running") is True]
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
            adapters_data = []
            if self.adapter_manager:
                adapters_data = await self.adapter_manager.list_adapters()
            
            # Get configuration
            config_data = await self._get_config_manager().get_config_value()
            
            # Get profiles
            profiles = await self._get_config_manager().list_profiles()
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

    # Service Management Methods
    async def get_service_registry_info(self, handler: Optional[str] = None, service_type: Optional[str] = None) -> Dict[str, Any]:
        """Get information about registered services in the service registry."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return {"error": "Service registry not available"}
            
            return self.runtime.service_registry.get_provider_info(handler, service_type)
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
                
            # This would require extending the service registry with update methods
            # For now, return not implemented
            return {
                "success": False,
                "error": "Service priority updates not yet implemented - requires service registry enhancements",
                "suggestion": "Service priorities are currently set during adapter service registration"
            }
        except Exception as e:
            logger.error(f"Failed to update service priority: {e}")
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
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to reset circuit breakers: {e}")
            await self._record_event("service_management", "reset_circuit_breakers", False, error=str(e))
            return {"success": False, "error": str(e)}

    async def get_service_health_status(self) -> Dict[str, Any]:
        """Get health status of all registered services."""
        try:
            if not self.runtime or not hasattr(self.runtime, 'service_registry') or self.runtime.service_registry is None:
                return {"error": "Service registry not available"}
                
            registry_info = self.runtime.service_registry.get_provider_info()
            health_status = {
                "overall_health": "healthy",
                "services": {},
                "circuit_breaker_states": {},
                "total_services": 0,
                "healthy_services": 0,
                "unhealthy_services": 0
            }
            
            # Process handler-specific services
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
            
            # Process global services
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
            
            # Set overall health
            if health_status["unhealthy_services"] > 0:
                if health_status["unhealthy_services"] > health_status["healthy_services"]:
                    health_status["overall_health"] = "unhealthy"
                else:
                    health_status["overall_health"] = "degraded"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Failed to get service health status: {e}")
            return {"error": str(e)}

    async def get_service_selection_explanation(self) -> Dict[str, Any]:
        """Get explanation of how service selection works with priorities and strategies."""
        return {
            "service_selection_logic": {
                "overview": "Services are selected using a multi-tier priority system with configurable selection strategies",
                "priority_groups": {
                    "description": "Services are first grouped by priority_group (0, 1, 2, etc.)",
                    "behavior": "Lower priority group numbers are tried first (0 before 1, 1 before 2, etc.)"
                },
                "priority_levels": {
                    "description": "Within each priority group, services have priority levels",
                    "levels": {
                        "CRITICAL": {"value": 0, "description": "Highest priority within group"},
                        "HIGH": {"value": 1, "description": "High priority within group"},
                        "NORMAL": {"value": 2, "description": "Normal priority within group (default)"},
                        "LOW": {"value": 3, "description": "Low priority within group"},
                        "FALLBACK": {"value": 9, "description": "Last resort within group"}
                    },
                    "behavior": "Lower priority values are tried first within each group"
                },
                "selection_strategies": {
                    "FALLBACK": {
                        "description": "Use first available healthy service in priority order",
                        "behavior": "Always tries services in the same priority order until one succeeds"
                    },
                    "ROUND_ROBIN": {
                        "description": "Rotate through services at same priority level",
                        "behavior": "Cycles through available services to distribute load evenly"
                    }
                },
                "circuit_breakers": {
                    "description": "Each service has a circuit breaker for fault tolerance",
                    "states": {
                        "CLOSED": "Service is healthy and accepting requests",
                        "OPEN": "Service is failing and temporarily unavailable",
                        "HALF_OPEN": "Service is being tested for recovery"
                    }
                },
                "selection_flow": [
                    "1. Group services by priority_group (0, 1, 2, etc.)",
                    "2. For each priority group (starting with lowest number):",
                    "   a. Sort services by priority level (CRITICAL=0, HIGH=1, etc.)",
                    "   b. Apply selection strategy (FALLBACK or ROUND_ROBIN)",
                    "   c. Check circuit breaker status",
                    "   d. Verify service health",
                    "   e. Return first healthy service found",
                    "3. If no services found, move to next priority group",
                    "4. If no services available in any group, return None"
                ]
            },
            "example_scenarios": {
                "fallback_strategy": {
                    "description": "Two LLM services: OpenAI (CRITICAL) and LocalLLM (NORMAL)",
                    "behavior": "Always try OpenAI first, fall back to LocalLLM if OpenAI fails"
                },
                "round_robin_strategy": {
                    "description": "Three load-balanced API services all at NORMAL priority",
                    "behavior": "Rotate requests: API1 -> API2 -> API3 -> API1 -> ..."
                },
                "multi_group_example": {
                    "description": "Priority Group 0: Critical services, Priority Group 1: Backup services",
                    "behavior": "Only use Group 1 services if all Group 0 services are unavailable"
                }
            }
        }

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
