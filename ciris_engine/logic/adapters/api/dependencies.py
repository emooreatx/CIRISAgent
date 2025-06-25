"""
FastAPI dependency injection utilities for the API adapter.
"""
from typing import Optional, TypeVar, Type
from fastapi import Depends, HTTPException, status

from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.logic.registries.base import ServiceRegistry

T = TypeVar('T', bound=ServiceProtocol)

# Global service registry reference (set by API adapter on startup)
_service_registry: Optional[ServiceRegistry] = None

def set_service_registry(registry: ServiceRegistry) -> None:
    """Set the global service registry for dependency injection."""
    global _service_registry
    _service_registry = registry

def get_service_registry() -> ServiceRegistry:
    """Get the current service registry."""
    if _service_registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service registry not initialized"
        )
    return _service_registry

def get_service(service_type: Type[T]) -> T:
    """
    FastAPI dependency to get a service by type.
    
    Usage:
        @router.get("/example")
        async def example(
            memory_service: MemoryService = Depends(lambda: get_service(MemoryService))
        ):
            ...
    """
    registry = get_service_registry()
    
    # Try to get service by protocol type
    services = registry.get_services_by_type(service_type.__name__)
    if not services:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service {service_type.__name__} not available"
        )
    
    # Return the first available service
    return services[0]

def get_required_service(service_type: Type[T]) -> T:
    """
    Get a required service, raising an error if not found.
    
    This is stricter than get_service and should be used for
    services that are absolutely required for the endpoint to function.
    """
    service = get_service(service_type)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Required service {service_type.__name__} is not available"
        )
    return service

# Convenience dependencies for common services
async def get_memory_service():
    """Get the memory service."""
    from ciris_engine.protocols.services import MemoryServiceProtocol
    return get_service(MemoryServiceProtocol)

async def get_llm_service():
    """Get the LLM service."""
    from ciris_engine.protocols.services import LLMService
    return get_service(LLMService)

async def get_audit_service():
    """Get the audit service."""
    from ciris_engine.protocols.services import AuditServiceProtocol
    return get_service(AuditServiceProtocol)

async def get_telemetry_service():
    """Get the telemetry service."""
    from ciris_engine.protocols.services import TelemetryService
    return get_service(TelemetryService)