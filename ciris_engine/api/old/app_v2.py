"""CIRIS API v2.0 Application.

Complete rewrite with proper authentication, role-based access, and OAuth support.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ciris_engine.api.routes import (
    api_auth_v2,
    api_emergency,
    api_health,
    api_cognitive,
    api_memory,
    api_messages,
    api_telemetry,
    api_runtime,
    api_config,
    api_incidents,
    api_self_config,
    api_wise,
    api_audit,
    api_agent,
    api_tools
)
from ciris_engine.api.services.auth_service import APIAuthService
from ciris_engine.api.security.emergency import EmergencyShutdownVerifier

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting CIRIS API v2.0")
    
    # Initialize auth service
    app.state.auth_service = APIAuthService()
    
    # Initialize emergency verifier (will be configured with keys later)
    app.state.emergency_verifier = EmergencyShutdownVerifier({})
    
    yield
    
    # Shutdown
    logger.info("Shutting down CIRIS API v2.0")

def create_app(runtime=None) -> FastAPI:
    """Create FastAPI application with all routes."""
    app = FastAPI(
        title="CIRIS API",
        version="2.0.0",
        description="Cognitive Intelligence Research and Implementation System API",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store runtime if provided
    if runtime:
        app.state.runtime = runtime
    
    # Include routers
    app.include_router(api_auth_v2.router, prefix="/v2")
    app.include_router(api_emergency.router, prefix="/v2")
    app.include_router(api_health.router, prefix="/v2")
    app.include_router(api_cognitive.router, prefix="/v2")
    app.include_router(api_memory.router, prefix="/v2")
    app.include_router(api_messages.router, prefix="/v2")
    app.include_router(api_telemetry.router, prefix="/v2")
    app.include_router(api_runtime.router, prefix="/v2")
    app.include_router(api_config.router, prefix="/v2")
    app.include_router(api_incidents.router, prefix="/v2")
    app.include_router(api_self_config.router, prefix="/v2")
    app.include_router(api_wise.router, prefix="/v2")
    app.include_router(api_audit.router, prefix="/v2")
    app.include_router(api_agent.router, prefix="/v2")
    app.include_router(api_tools.router, prefix="/v2")
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    return app

def initialize_app_services(app: FastAPI, runtime):
    """Initialize app services from runtime."""
    if not runtime:
        logger.warning("No runtime provided to API")
        return
    
    # Get services from runtime
    try:
        # Core services
        app.state.config_service = runtime.bus_manager.get_service('config')
        app.state.memory_service = runtime.bus_manager.get_service('memory')
        app.state.audit_service = runtime.bus_manager.get_service('audit')
        app.state.telemetry_service = runtime.bus_manager.get_service('telemetry')
        app.state.incident_service = runtime.bus_manager.get_service('incident_management')
        app.state.shutdown_service = runtime.bus_manager.get_service('shutdown')
        
        # Optional services
        app.state.wise_service = runtime.bus_manager.get_service('wise_authority')
        app.state.runtime_control = runtime.bus_manager.get_service('runtime_control')
        
        # Initialize emergency system with trusted keys
        if app.state.config_service:
            # Get trusted keys
            trusted_keys = {}
            root_key = app.state.config_service.get_config("wa_root_key")
            if root_key:
                trusted_keys["ROOT"] = root_key
            
            authority_keys = app.state.config_service.get_config("wa_authority_keys") or {}
            trusted_keys.update(authority_keys)
            
            # Update emergency verifier
            app.state.emergency_verifier = EmergencyShutdownVerifier(trusted_keys)
        
        # Store essential config
        app.state.essential_config = runtime.essential_config
        
        logger.info("API services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize API services: {e}")

# Create default app instance
app = create_app()