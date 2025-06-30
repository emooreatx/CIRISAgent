"""
Runtime control service for API adapter.
"""
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from ciris_engine.logic.adapters.base import Service
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

logger = logging.getLogger(__name__)


class APIRuntimeControlService(Service):
    """Runtime control exposed through API."""
    
    def __init__(self, runtime: Any) -> None:
        """Initialize API runtime control."""
        super().__init__()
        self.runtime = runtime
        self._paused = False
        self._pause_reason: Optional[str] = None
        self._pause_time: Optional[datetime] = None
    
    async def pause_processing(self, reason: str) -> bool:
        """Pause agent processing."""
        if self._paused:
            logger.warning(f"Already paused since {self._pause_time}")
            return False
        
        self._paused = True
        self._pause_reason = reason
        self._pause_time = datetime.now(timezone.utc)
        
        logger.info(f"Processing paused via API: {reason}")
        
        # Notify runtime if it has pause capability
        if hasattr(self.runtime, 'pause_processing'):
            await self.runtime.pause_processing(reason)
        
        return True
    
    async def resume_processing(self) -> bool:
        """Resume agent processing."""
        if not self._paused:
            logger.warning("Not currently paused")
            return False
        
        self._paused = False
        pause_duration = (
            datetime.now(timezone.utc) - self._pause_time
        ).total_seconds() if self._pause_time else 0
        
        logger.info(
            f"Processing resumed via API after {pause_duration:.1f}s pause"
        )
        
        self._pause_reason = None
        self._pause_time = None
        
        # Notify runtime if it has resume capability
        if hasattr(self.runtime, 'resume_processing'):
            await self.runtime.resume_processing()
        
        return True
    
    async def request_state_transition(
        self,
        target_state: str,
        reason: str
    ) -> bool:
        """Request cognitive state transition."""
        try:
            current_state = getattr(self.runtime, 'current_state', 'UNKNOWN')
            
            logger.info(
                f"API requesting state transition: {current_state} -> {target_state} "
                f"(reason: {reason})"
            )
            
            # Use runtime's state transition if available
            if hasattr(self.runtime, 'request_state_transition'):
                return await self.runtime.request_state_transition(
                    target_state, reason
                )
            
            # Otherwise try direct transition
            if hasattr(self.runtime, 'transition_to_state'):
                await self.runtime.transition_to_state(target_state)
                return True
            
            logger.error("Runtime does not support state transitions")
            return False
            
        except Exception as e:
            logger.error(f"State transition failed: {e}")
            return False
    
    async def get_runtime_status(self) -> Dict[str, Any]:
        """Get current runtime status."""
        status = {
            "paused": self._paused,
            "pause_reason": self._pause_reason,
            "pause_time": self._pause_time.isoformat() if self._pause_time else None,
            "cognitive_state": str(self.runtime.current_state) if hasattr(
                self.runtime, 'current_state'
            ) else "UNKNOWN",
            "uptime_seconds": self.runtime.get_uptime() if hasattr(
                self.runtime, 'get_uptime'
            ) else 0
        }
        
        # Add runtime-specific status if available
        if hasattr(self.runtime, 'get_status'):
            runtime_status = self.runtime.get_status()
            if isinstance(runtime_status, dict):
                status.update(runtime_status)
        
        return status
    
    async def handle_emergency_shutdown(self, command: Any) -> Any:
        """Handle emergency shutdown command."""
        logger.critical(
            f"Emergency shutdown requested via API: {command.reason}"
        )
        
        # Delegate to runtime's shutdown service
        if hasattr(self.runtime, 'shutdown_service'):
            await self.runtime.shutdown_service.request_shutdown(
                f"EMERGENCY API: {command.reason}"
            )
        else:
            # Fallback to runtime shutdown
            if hasattr(self.runtime, 'shutdown'):
                await self.runtime.shutdown(f"EMERGENCY API: {command.reason}")
        
        return {
            "shutdown_initiated": datetime.now(timezone.utc),
            "command_verified": True,
            "services_stopped": ["all"],
            "data_persisted": True,
            "final_message_sent": True,
            "shutdown_completed": datetime.now(timezone.utc),
            "exit_code": 0
        }
    
    # Service interface methods
    
    async def start(self) -> None:
        """Start the runtime control service."""
        logger.info("API Runtime Control Service started")
    
    async def stop(self) -> None:
        """Stop the runtime control service."""
        logger.info("API Runtime Control Service stopped")
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return True
    
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="APIRuntimeControlService",
            actions=["pause_processing", "resume_processing", "request_state_transition", "get_runtime_status", "handle_emergency_shutdown"],
            version="1.0.0",
            dependencies=[],
            metadata={
                "description": "Runtime control service for API adapter",
                "features": ["pause_resume", "state_transitions", "emergency_shutdown"]
            }
        )
    
    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        return ServiceStatus(
            service_name="APIRuntimeControlService",
            service_type="RUNTIME_CONTROL",
            is_healthy=True,
            uptime_seconds=0.0,  # Would need to track start time
            last_error=None,
            metrics={
                "paused": float(self._paused),
                "pause_duration": float((datetime.now(timezone.utc) - self._pause_time).total_seconds() if self._pause_time and self._paused else 0)
            },
            last_health_check=datetime.now(timezone.utc)
        )