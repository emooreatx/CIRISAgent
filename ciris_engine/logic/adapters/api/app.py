"""
FastAPI application for CIRIS API v1.

This module creates and configures the FastAPI application with all routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Any

# Import all route modules from adapter
from .routes import (
    agent, audit, auth, config, emergency,
    memory, system, telemetry, wa, system_extensions, users
)

# Import auth service
from .services.auth_service import APIAuthService

# Import rate limiting middleware
from .middleware.rate_limiter import RateLimitMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("Starting CIRIS API...")
    yield
    # Shutdown
    print("Shutting down CIRIS API...")

def create_app(runtime: Any = None, config: Any = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    Args:
        runtime: Optional runtime instance for service access
        config: Optional APIAdapterConfig instance

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="CIRIS API v1",
        description="Autonomous AI Agent Interaction and Observability API (Pre-Beta)",
        version="1.0.0",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on deployment
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add rate limiting middleware if enabled in config
    if config and getattr(config, 'rate_limit_enabled', False):
        rate_limit = getattr(config, 'rate_limit_per_minute', 60)
        app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)
        print(f"Rate limiting enabled: {rate_limit} requests per minute")

    # Store runtime in app state for access in routes
    if runtime:
        app.state.runtime = runtime
        
        # Initialize auth service
        app.state.auth_service = APIAuthService()
        
        # Services will be injected later in ApiPlatform.start() after they're initialized
        # For now, just set placeholders to None
        app.state.memory_service = None
        app.state.time_service = None
        app.state.telemetry_service = None
        app.state.audit_service = None
        app.state.config_service = None
        app.state.wise_authority_service = None
        app.state.wa_service = None
        app.state.resource_monitor = None
        app.state.task_scheduler = None
        app.state.authentication_service = None
        app.state.incident_management_service = None
        app.state.service_registry = None
        app.state.agent_processor = None
        app.state.message_handler = None

    # Mount v1 API routes (all routes except emergency under /v1)
    v1_routers = [
        agent.router,      # Agent interaction
        memory.router,     # Memory operations  
        system.router,     # System operations (includes health, time, resources, runtime)
        system_extensions.router,  # Extended system operations (queue, services, processors)
        config.router,     # Configuration management
        telemetry.router,  # Telemetry & observability
        audit.router,      # Audit trail
        wa.router,         # Wise Authority
        auth.router,       # Authentication
        users.router,      # User management
    ]

    # Include all v1 routes with /v1 prefix
    for router in v1_routers:
        app.include_router(router, prefix="/v1")

    # Mount emergency routes at root level (no /v1 prefix)
    # This is special - requires signed commands, no auth
    app.include_router(emergency.router)

    return app

# For running standalone (development)
if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)