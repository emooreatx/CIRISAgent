"""
FastAPI application for CIRIS API v1.

This module creates and configures the FastAPI application with all routes.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Any

# Import all route modules
from ciris_engine.api.routes import (
    adaptation, agent, audit, auth, config, emergency,
    filters, health, incidents, init, llm, memory,
    observe, resources, runtime, scheduler, secrets,
    shutdown, stream, telemetry, time, tools, tsdb,
    visibility, wa
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    print("Starting CIRIS API...")
    yield
    # Shutdown
    print("Shutting down CIRIS API...")

def create_app(runtime: Any = None) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        runtime: Optional runtime instance for service access
        
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="CIRIS API",
        description="Autonomous AI Agent Control and Observability API",
        version="2.0.0",
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
    
    # Store runtime in app state for access in routes
    if runtime:
        app.state.runtime = runtime
    
    # Mount v1 API routes (all routes except emergency under /v1)
    v1_routers = [
        health.router,
        auth.router,
        agent.router,
        memory.router,
        llm.router,
        audit.router,
        config.router,
        telemetry.router,
        incidents.router,
        tsdb.router,
        secrets.router,
        time.router,
        shutdown.router,
        init.router,
        visibility.router,
        resources.router,
        runtime.router,
        wa.router,
        adaptation.router,
        filters.router,
        scheduler.router,
        tools.router,
        observe.router,
        stream.router,
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