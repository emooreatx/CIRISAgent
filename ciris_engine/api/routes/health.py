"""
Health check endpoints for CIRIS API.
"""
from fastapi import APIRouter, Request
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import BaseModel, Field
import asyncio

from ciris_engine.schemas.api.responses import SuccessResponse

router = APIRouter(prefix="/health", tags=["health"])

class HealthStatus(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current server time")
    services: Dict[str, Dict[str, int]] = Field(..., description="Service health summary")

@router.get("", response_model=SuccessResponse[HealthStatus])
async def health_check(request: Request):
    """
    Health check endpoint.
    
    Returns current system health and service availability.
    """
    health_status = HealthStatus(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(timezone.utc),
        services={}
    )
    
    # Check service health if available
    if hasattr(request.app.state, 'service_registry'):
        service_registry = request.app.state.service_registry
        try:
            from ciris_engine.schemas.runtime.enums import ServiceType
            for service_type in ServiceType:
                providers = service_registry.get_services_by_type(service_type)
                if providers:
                    healthy_count = 0
                    for provider in providers:
                        try:
                            if hasattr(provider, "is_healthy"):
                                if asyncio.iscoroutinefunction(provider.is_healthy):
                                    is_healthy = await provider.is_healthy()
                                else:
                                    is_healthy = provider.is_healthy()
                                if is_healthy:
                                    healthy_count += 1
                            else:
                                healthy_count += 1  # Assume healthy if no method
                        except:
                            pass  # Count as unhealthy if check fails
                    
                    health_status.services[service_type.value] = {
                        "available": len(providers),
                        "healthy": healthy_count
                    }
        except Exception as e:
            # Log but don't fail health check
            import logging
            logging.error(f"Error checking service health: {e}")
    
    return SuccessResponse(data=health_status)