"""
API observer for tracking API events and metrics.
"""
import logging
from typing import Any, Optional, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class APIObserver:
    """Observer for API adapter events."""
    
    def __init__(self, adapter_id: str, runtime: Any) -> None:
        """Initialize API observer."""
        self.adapter_id = adapter_id
        self.runtime = runtime
        self.request_count = 0
        self.response_count = 0
        self.error_count = 0
        self.websocket_connections = 0
        self.start_time = datetime.now(timezone.utc)
        
    async def start(self) -> None:
        """Start the API observer."""
        logger.info(f"API observer started for adapter: {self.adapter_id}")
    
    async def stop(self) -> None:
        """Stop the API observer."""
        logger.info(f"API observer stopped for adapter: {self.adapter_id}")
    
    async def observe_request(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Observe an incoming API request."""
        self.request_count += 1
        
        # Log to telemetry
        await self.memorize_metric(
            metric_name="api.request",
            value=1.0,
            tags={
                "endpoint": endpoint,
                "method": method,
                "user_id": user_id or "anonymous"
            }
        )
        
        # Log event
        logger.debug(f"API request: {method} {endpoint} from {user_id or 'anonymous'}")
    
    async def observe_response(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[str] = None
    ) -> None:
        """Observe an API response."""
        self.response_count += 1
        
        if status_code >= 400:
            self.error_count += 1
        
        # Log to telemetry
        await self.memorize_metric(
            metric_name="api.response",
            value=duration_ms,
            tags={
                "endpoint": endpoint,
                "method": method,
                "status": str(status_code),
                "user_id": user_id or "anonymous"
            }
        )
        
        # Log event
        logger.debug(
            f"API response: {method} {endpoint} -> {status_code} "
            f"({duration_ms:.1f}ms)"
        )
    
    async def observe_websocket_connect(self, client_id: str) -> None:
        """Observe WebSocket connection."""
        self.websocket_connections += 1
        
        await self.memorize_metric(
            metric_name="api.websocket.connect",
            value=1.0,
            tags={"client_id": client_id}
        )
        
        logger.info(f"WebSocket connected: {client_id}")
    
    async def observe_websocket_disconnect(self, client_id: str) -> None:
        """Observe WebSocket disconnection."""
        self.websocket_connections -= 1
        
        await self.memorize_metric(
            metric_name="api.websocket.disconnect",
            value=1.0,
            tags={"client_id": client_id}
        )
        
        logger.info(f"WebSocket disconnected: {client_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get observer statistics."""
        return {
            "adapter_id": self.adapter_id,
            "request_count": self.request_count,
            "response_count": self.response_count,
            "error_count": self.error_count,
            "websocket_connections": self.websocket_connections,
            "uptime_seconds": (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds()
        }
    
    async def memorize_metric(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send metric to telemetry service through runtime."""
        try:
            if hasattr(self.runtime, 'memorize_metric'):
                await self.runtime.memorize_metric(
                    metric_name=metric_name,
                    value=value,
                    tags=tags or {}
                )
        except Exception as e:
            logger.debug(f"Could not memorize metric {metric_name}: {e}")