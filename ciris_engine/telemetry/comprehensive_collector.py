"""
Comprehensive Telemetry Collector

Implements the TelemetryInterface protocol to collect detailed system state
including adapters, services, configuration, and processor information.
"""

import asyncio
import logging
import psutil
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union

from ciris_engine.protocols.telemetry_interface import (
    TelemetryInterface,
    ProcessorControlInterface,
    TelemetrySnapshot,
    AdapterInfo,
    ServiceInfo,
    ProcessorState,
    ConfigurationSnapshot
)
from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry
from ciris_engine.telemetry.core import TelemetryService


logger = logging.getLogger(__name__)


class ComprehensiveTelemetryCollector(TelemetryInterface, ProcessorControlInterface):
    """Comprehensive telemetry collector with processor control capabilities"""
    
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.start_time = datetime.now(timezone.utc)
        
    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        """Get a complete snapshot of current system telemetry"""
        try:
            # Gather all components
            basic_telemetry = await self._get_basic_telemetry()
            adapters = await self.get_adapters_info()
            services = await self.get_services_info()
            processor_state = await self.get_processor_state()
            configuration = await self.get_configuration_snapshot()
            
            # Runtime metrics
            uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            memory_mb = psutil.virtual_memory().used / 1024 / 1024
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Health assessment
            health_status = await self.get_health_status()
            
            return TelemetrySnapshot(
                basic_telemetry=basic_telemetry,
                adapters=adapters,
                services=services,
                processor_state=processor_state,
                configuration=configuration,
                runtime_uptime_seconds=uptime,
                memory_usage_mb=memory_mb,
                cpu_usage_percent=cpu_percent,
                overall_health=health_status.get("overall", "unknown"),
                health_details=health_status.get("details", {})
            )
        except Exception as e:
            logger.error(f"Failed to collect telemetry snapshot: {e}")
            # Return minimal snapshot on error
            return TelemetrySnapshot(
                basic_telemetry=CompactTelemetry(),
                processor_state=ProcessorState(),
                configuration=ConfigurationSnapshot(profile_name="unknown"),
                overall_health="error",
                health_details={"error": str(e)}
            )
    
    async def get_adapters_info(self) -> List[AdapterInfo]:
        """Get information about all registered adapters"""
        adapters = []
        try:
            if hasattr(self.runtime, 'adapters') and self.runtime.adapters:
                for adapter in self.runtime.adapters:
                    adapter_info = AdapterInfo(
                        name=adapter.__class__.__name__,
                        type=getattr(adapter, 'adapter_type', 'unknown'),
                        status=await self._get_adapter_status(adapter),
                        capabilities=getattr(adapter, 'capabilities', []),
                        metadata={
                            "class": adapter.__class__.__name__,
                            "module": adapter.__class__.__module__,
                            "instance_id": str(id(adapter))
                        }
                    )
                    adapters.append(adapter_info)
        except Exception as e:
            logger.error(f"Failed to collect adapter info: {e}")
            
        return adapters
    
    async def get_services_info(self) -> List[ServiceInfo]:
        """Get information about all registered services"""
        services = []
        try:
            if hasattr(self.runtime, 'service_registry') and self.runtime.service_registry:
                registry = self.runtime.service_registry
                
                # Collect handler-specific services
                if hasattr(registry, '_providers'):
                    for handler, service_types in registry._providers.items():
                        for service_type, providers in service_types.items():
                            for provider in providers:
                                service_info = ServiceInfo(
                                    name=provider.name,
                                    service_type=service_type,
                                    handler=handler,
                                    priority=provider.priority.name,
                                    capabilities=provider.capabilities,
                                    status=await self._get_service_health(provider),
                                    circuit_breaker_state=self._get_circuit_breaker_state(provider),
                                    metadata=provider.metadata or {},
                                    instance_id=str(id(provider.instance))
                                )
                                services.append(service_info)
                
                # Collect global services
                if hasattr(registry, '_global_services'):
                    for service_type, providers in registry._global_services.items():
                        for provider in providers:
                            service_info = ServiceInfo(
                                name=provider.name,
                                service_type=service_type,
                                handler=None,  # Global service
                                priority=provider.priority.name,
                                capabilities=provider.capabilities,
                                status=await self._get_service_health(provider),
                                circuit_breaker_state=self._get_circuit_breaker_state(provider),
                                metadata=provider.metadata or {},
                                instance_id=str(id(provider.instance))
                            )
                            services.append(service_info)
                            
        except Exception as e:
            logger.error(f"Failed to collect service info: {e}")
            
        return services
    
    async def get_processor_state(self) -> ProcessorState:
        """Get current processor state information"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                
                # Get basic state - check if processor is actively running
                # First check if processor has an active processing task
                has_active_task = (
                    hasattr(processor, '_processing_task') and 
                    processor._processing_task is not None and 
                    not processor._processing_task.done()
                )
                
                # Check if processor is in a running state (not SHUTDOWN)
                from ciris_engine.schemas.states_v1 import AgentState
                current_state = None
                if hasattr(processor, 'state_manager') and processor.state_manager:
                    current_state = processor.state_manager.get_state()
                
                is_running = (
                    has_active_task and 
                    current_state is not None and 
                    current_state != AgentState.SHUTDOWN
                )
                current_round = getattr(processor, 'current_round', 0)
                
                # Get queue information if available
                thoughts_pending = 0
                thoughts_processing = 0
                if hasattr(processor, 'processing_queue'):
                    queue = processor.processing_queue
                    thoughts_pending = getattr(queue, 'size', 0)
                
                return ProcessorState(
                    is_running=is_running,
                    current_round=current_round,
                    thoughts_pending=thoughts_pending,
                    thoughts_processing=thoughts_processing,
                    processor_mode=await self._get_processor_mode(),
                    last_activity=datetime.now(timezone.utc) if is_running else None
                )
        except Exception as e:
            logger.error(f"Failed to get processor state: {e}")
            
        return ProcessorState()
    
    async def get_configuration_snapshot(self) -> ConfigurationSnapshot:
        """Get current system configuration"""
        try:
            config = ConfigurationSnapshot(profile_name="unknown")
            
            if hasattr(self.runtime, 'profile') and self.runtime.profile:
                config.profile_name = self.runtime.profile.name
                
            if hasattr(self.runtime, 'startup_channel_id'):
                config.startup_channel_id = self.runtime.startup_channel_id
                
            if hasattr(self.runtime, 'app_config') and self.runtime.app_config:
                app_config = self.runtime.app_config
                
                # LLM configuration
                if hasattr(app_config, 'llm_services') and hasattr(app_config.llm_services, 'openai'):
                    llm_config = app_config.llm_services.openai
                    config.llm_model = getattr(llm_config, 'model_name', None)
                    config.llm_base_url = getattr(llm_config, 'api_base', None)
                
                # Adapter modes
                if hasattr(self.runtime, 'adapters'):
                    config.adapter_modes = [adapter.__class__.__name__ for adapter in self.runtime.adapters]
                
                # Debug mode
                config.debug_mode = getattr(app_config, 'debug', False)
                
            return config
            
        except Exception as e:
            logger.error(f"Failed to get configuration snapshot: {e}")
            return ConfigurationSnapshot(profile_name="error")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status"""
        health_details = {}
        overall_health = "healthy"
        
        try:
            # Check adapter health
            adapters = await self.get_adapters_info()
            active_adapters = [a for a in adapters if a.status == "active"]
            if len(adapters) == 0:
                health_details["adapters"] = "no_adapters"
                overall_health = "critical"
            elif len(active_adapters) == 0:
                health_details["adapters"] = "no_active_adapters"
                overall_health = "critical"
            elif len(active_adapters) < len(adapters):
                health_details["adapters"] = "some_adapters_inactive"
                if overall_health == "healthy":
                    overall_health = "degraded"
            else:
                health_details["adapters"] = "all_active"
            
            # Check service health
            services = await self.get_services_info()
            healthy_services = [s for s in services if s.status == "healthy"]
            if len(healthy_services) < len(services) * 0.8:  # 80% threshold
                health_details["services"] = "degraded_services"
                overall_health = "critical"
            else:
                health_details["services"] = "services_healthy"
            
            # Check processor state
            processor_state = await self.get_processor_state()
            if processor_state.is_running:
                health_details["processor"] = "running"
            else:
                health_details["processor"] = "not_running"
                if overall_health == "healthy":
                    overall_health = "degraded"
                    
        except Exception as e:
            logger.error(f"Failed to assess health status: {e}")
            overall_health = "error"
            health_details["error"] = str(e)
        
        return {
            "overall": overall_health,
            "details": health_details
        }
    
    async def record_metric(self, metric_name: str, value: Union[int, float], tags: Optional[Dict[str, str]] = None) -> None:
        """Record a custom metric with optional tags"""
        try:
            if hasattr(self.runtime, 'telemetry_service') and self.runtime.telemetry_service:
                await self.runtime.telemetry_service.record_metric(metric_name, float(value), tags)
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
    
    async def get_metrics_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric"""
        try:
            if hasattr(self.runtime, 'telemetry_service') and self.runtime.telemetry_service:
                telemetry_service = self.runtime.telemetry_service
                
                # Get enhanced history if available
                if hasattr(telemetry_service, '_enhanced_history') and metric_name in telemetry_service._enhanced_history:
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                    history = []
                    
                    for entry in telemetry_service._enhanced_history[metric_name]:
                        if entry['timestamp'] > cutoff_time:
                            history.append({
                                'timestamp': entry['timestamp'].isoformat(),
                                'value': entry['value'],
                                'tags': entry['tags']
                            })
                    
                    return sorted(history, key=lambda x: x['timestamp'])
                
                # Fallback to basic history
                elif hasattr(telemetry_service, '_history') and metric_name in telemetry_service._history:
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
                    history = []
                    
                    for timestamp, value in telemetry_service._history[metric_name]:
                        if timestamp > cutoff_time:
                            history.append({
                                'timestamp': timestamp.isoformat(),
                                'value': value,
                                'tags': {}
                            })
                    
                    return sorted(history, key=lambda x: x['timestamp'])
                    
        except Exception as e:
            logger.error(f"Failed to get metrics history for {metric_name}: {e}")
        
        return []
    
    # Processor Control Methods
    
    async def single_step(self) -> Dict[str, Any]:
        """Execute a single processing step and return results"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                
                # Get current state before processing
                before_state = await self.get_processor_state()
                start_time = datetime.now(timezone.utc)
                
                # Execute a single processing round
                round_number = getattr(processor, 'current_round', 0) + 1
                
                # Call the existing process method with a single round
                if hasattr(processor, 'process'):
                    processing_result = await processor.process(round_number)
                    
                    # Get state after processing
                    after_state = await self.get_processor_state()
                    end_time = datetime.now(timezone.utc)
                    
                    # Build detailed result
                    result = {
                        "status": "completed",
                        "round_number": round_number,
                        "execution_time_ms": int((end_time - start_time).total_seconds() * 1000),
                        "before_state": {
                            "thoughts_pending": before_state.thoughts_pending,
                            "thoughts_processing": before_state.thoughts_processing,
                            "current_round": before_state.current_round
                        },
                        "after_state": {
                            "thoughts_pending": after_state.thoughts_pending,
                            "thoughts_processing": after_state.thoughts_processing,
                            "current_round": after_state.current_round
                        },
                        "processing_result": processing_result if processing_result else "no_result",
                        "timestamp": start_time.isoformat()
                    }
                    
                    # Add change summary
                    thoughts_processed = before_state.thoughts_pending - after_state.thoughts_pending
                    result["summary"] = {
                        "thoughts_processed": max(0, thoughts_processed),
                        "round_completed": True,
                        "processing_time_ms": result["execution_time_ms"]
                    }
                    
                    return result
                else:
                    return {
                        "status": "error",
                        "error": "Processor does not have process method available"
                    }
        except Exception as e:
            logger.error(f"Failed to execute single step: {e}")
            return {
                "status": "error", 
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def pause_processing(self) -> bool:
        """Pause the processor"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                if hasattr(processor, 'stop_processing'):
                    await processor.stop_processing()
                    return True
        except Exception as e:
            logger.error(f"Failed to pause processing: {e}")
        
        return False
    
    async def resume_processing(self) -> bool:
        """Resume the processor"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                if hasattr(processor, 'start_processing'):
                    await processor.start_processing()
                    return True
        except Exception as e:
            logger.error(f"Failed to resume processing: {e}")
        
        return False
    
    async def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get current processing queue status"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                if hasattr(processor, 'processing_queue'):
                    queue = processor.processing_queue
                    return {
                        "size": getattr(queue, 'size', 0),
                        "capacity": getattr(queue, 'capacity', "unknown"),
                        "oldest_item_age": "unknown"  # Would need to be implemented
                    }
        except Exception as e:
            logger.error(f"Failed to get processing queue status: {e}")
        
        return {"status": "unavailable"}
    
    # Helper methods
    
    async def _get_basic_telemetry(self) -> CompactTelemetry:
        """Get basic telemetry from the existing service"""
        try:
            if hasattr(self.runtime, 'telemetry_service') and self.runtime.telemetry_service:
                # Create a dummy system snapshot to get telemetry updated
                from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
                snapshot = SystemSnapshot()
                await self.runtime.telemetry_service.update_system_snapshot(snapshot)
                return snapshot.telemetry or CompactTelemetry()
        except Exception as e:
            logger.error(f"Failed to get basic telemetry: {e}")
        
        return CompactTelemetry()
    
    async def _get_adapter_status(self, adapter: Any) -> str:
        """Determine adapter status"""
        try:
            if hasattr(adapter, 'is_healthy'):
                is_healthy = await adapter.is_healthy()
                return "active" if is_healthy else "error"
            elif hasattr(adapter, '_running'):
                return "active" if adapter._running else "inactive"
            else:
                # If adapter is in runtime.adapters list, assume it's active
                return "active"
        except Exception:
            return "error"
    
    async def _get_service_health(self, provider: Any) -> str:
        """Get service health status"""
        try:
            # Check for is_healthy() method (HealthCheckProtocol)
            if hasattr(provider.instance, 'is_healthy'):
                try:
                    is_healthy = await provider.instance.is_healthy()
                    return "healthy" if is_healthy else "degraded"
                except Exception as e:
                    logger.debug(f"is_healthy() failed for {provider.name}: {e}")
                    # Fall through to other checks
            
            # Check for get_health() method (like AdaptiveFilterService)
            if hasattr(provider.instance, 'get_health'):
                try:
                    health_result = await provider.instance.get_health()
                    # Handle different return types
                    if hasattr(health_result, 'is_healthy'):
                        return "healthy" if health_result.is_healthy else "degraded"
                    elif isinstance(health_result, dict):
                        if health_result.get('is_healthy') or health_result.get('status') == 'healthy':
                            return "healthy"
                        else:
                            return "degraded"
                    else:
                        return "healthy"  # If method exists and doesn't error, assume healthy
                except Exception as e:
                    logger.debug(f"get_health() failed for {provider.name}: {e}")
                    # Fall through to other checks
            
            # Check for health_check() method (base Service class)
            if hasattr(provider.instance, 'health_check'):
                try:
                    health_result = await provider.instance.health_check()
                    # Base Service.health_check returns dict with status
                    if isinstance(health_result, dict):
                        status = health_result.get('status', 'unknown')
                        return "healthy" if status == "healthy" else "degraded"
                    else:
                        return "healthy"  # If method exists and doesn't error, assume healthy
                except Exception as e:
                    logger.debug(f"health_check() failed for {provider.name}: {e}")
                    # Fall through to circuit breaker check
            
            # Check circuit breaker state as fallback
            if hasattr(provider, 'circuit_breaker') and provider.circuit_breaker:
                state = provider.circuit_breaker.state
                # CircuitState enum values need to be converted to string
                state_value = state.value if hasattr(state, 'value') else str(state)
                if state_value == "closed":
                    return "healthy"
                elif state_value == "half_open":
                    return "degraded"
                else:
                    return "failed"
            
            # If service is registered and no explicit health check available, assume healthy
            return "healthy"
            
        except Exception as e:
            logger.warning(f"Error checking health for service {provider.name}: {e}")
            return "degraded"
    
    def _get_circuit_breaker_state(self, provider: Any) -> str:
        """Get circuit breaker state"""
        try:
            if hasattr(provider, 'circuit_breaker') and provider.circuit_breaker:
                state = provider.circuit_breaker.state
                # CircuitState enum values need to be converted to string
                return state.value if hasattr(state, 'value') else str(state)
        except Exception:
            pass
        return "unknown"
    
    async def _get_processor_mode(self) -> str:
        """Determine current processor mode"""
        try:
            if hasattr(self.runtime, 'agent_processor') and self.runtime.agent_processor:
                processor = self.runtime.agent_processor
                # This would need processor introspection capability
                return "work"  # Default assumption
        except Exception:
            pass
        return "unknown"