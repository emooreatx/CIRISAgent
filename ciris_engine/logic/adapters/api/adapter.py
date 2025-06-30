"""
API adapter for CIRIS v1.

Provides RESTful API and WebSocket interfaces to the CIRIS agent.
"""
import asyncio
import logging
from typing import Any, List, Optional
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ciris_engine.logic.adapters.base import Service
from ciris_engine.logic.registries.base import Priority
from ciris_engine.schemas.adapters import AdapterServiceRegistration
from ciris_engine.schemas.runtime.enums import ServiceType
from .app import create_app
from .config import APIAdapterConfig
from .api_runtime_control import APIRuntimeControlService
from .api_observer import APIObserver
from .api_communication import APICommunicationService

logger = logging.getLogger(__name__)


class ApiPlatform(Service):
    """API adapter platform for CIRIS v1."""
    
    config: APIAdapterConfig
    
    def __init__(self, runtime: Any, **kwargs: Any) -> None:
        """Initialize API adapter."""
        super().__init__(config=kwargs.get('adapter_config'))
        self.runtime = runtime
        
        # Parse configuration
        if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
            if isinstance(kwargs["adapter_config"], APIAdapterConfig):
                self.config = kwargs["adapter_config"]
            elif isinstance(kwargs["adapter_config"], dict):
                self.config = APIAdapterConfig(**kwargs["adapter_config"])
            else:
                self.config = APIAdapterConfig()
        else:
            self.config = APIAdapterConfig()
        
        # Load environment variables
        self.config.load_env_vars()
        
        # Create FastAPI app - services will be injected later in start()
        self.app = create_app(runtime)
        self._server = None
        self._server_task = None
        
        # Observer for API events
        self.observer = APIObserver(adapter_id="api", runtime=runtime)
        
        # Communication service for API responses
        self.communication = APICommunicationService()
        
        # Runtime control service
        self.runtime_control = APIRuntimeControlService(runtime)
        
        logger.info(
            f"API adapter initialized - host: {self.config.host}, "
            f"port: {self.config.port}"
        )
    
    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Get services provided by this adapter."""
        registrations = []
        
        # Register communication service
        registrations.append(
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.communication,
                priority=Priority.NORMAL,
                capabilities=['send_message']
            )
        )
        
        # Register runtime control service
        registrations.append(
            AdapterServiceRegistration(
                service_type=ServiceType.RUNTIME_CONTROL,
                provider=self.runtime_control,
                priority=Priority.HIGH,
                capabilities=['pause_processing', 'resume_processing', 'request_state_transition', 'get_runtime_status']
            )
        )
        
        return registrations
    
    def get_observer(self) -> Any:
        """Get the observer for this adapter."""
        return self.observer
    
    def _inject_services(self) -> None:
        """Inject services into FastAPI app state after initialization."""
        runtime = self.runtime
        logger.info("Injecting services into FastAPI app state...")
        
        # Store commonly accessed services
        if hasattr(runtime, 'memory_service') and runtime.memory_service is not None:
            self.app.state.memory_service = runtime.memory_service
            logger.info("Injected memory_service")
        if hasattr(runtime, 'time_service') and runtime.time_service is not None:
            self.app.state.time_service = runtime.time_service
            logger.info("Injected time_service")
        if hasattr(runtime, 'telemetry_service') and runtime.telemetry_service is not None:
            self.app.state.telemetry_service = runtime.telemetry_service
            logger.info("Injected telemetry_service")
        if hasattr(runtime, 'audit_service') and runtime.audit_service is not None:
            self.app.state.audit_service = runtime.audit_service
            logger.info("Injected audit_service")
        if hasattr(runtime, 'config_service') and runtime.config_service is not None:
            self.app.state.config_service = runtime.config_service
            logger.info("Injected config_service")
        if hasattr(runtime, 'wa_auth_system') and runtime.wa_auth_system is not None:
            self.app.state.wise_authority_service = runtime.wa_auth_system
            self.app.state.wa_service = runtime.wa_auth_system
            logger.info("Injected wise_authority_service")
        if hasattr(runtime, 'resource_monitor') and runtime.resource_monitor is not None:
            self.app.state.resource_monitor = runtime.resource_monitor
            logger.info("Injected resource_monitor")
        if hasattr(runtime, 'task_scheduler') and runtime.task_scheduler is not None:
            self.app.state.task_scheduler = runtime.task_scheduler
            logger.info("Injected task_scheduler")
        if hasattr(runtime, 'authentication_service') and runtime.authentication_service is not None:
            self.app.state.authentication_service = runtime.authentication_service
            logger.info("Injected authentication_service")
        if hasattr(runtime, 'incident_management_service') and runtime.incident_management_service is not None:
            self.app.state.incident_management_service = runtime.incident_management_service
            logger.info("Injected incident_management_service")
        if hasattr(runtime, 'service_registry') and runtime.service_registry is not None:
            self.app.state.service_registry = runtime.service_registry
            logger.info("Injected service_registry")
        
        # Inject runtime control service created by adapter
        self.app.state.runtime_control_service = self.runtime_control
        logger.info("Injected runtime_control_service")
        
        # Set up message handler function
        if hasattr(runtime, 'process_message'):
            self.app.state.on_message = runtime.process_message
            logger.info("Set up on_message handler")
        elif hasattr(runtime, 'agent_processor') and hasattr(runtime.agent_processor, 'process_message'):
            self.app.state.on_message = runtime.agent_processor.process_message
            logger.info("Set up on_message handler from agent_processor")
        else:
            # Create a simple mock handler for API mode
            # Store message history for the mock handler
            self.app.state.message_history = []
            
            async def mock_handler(msg):
                logger.info(f"Mock handler received message: {msg.content}")
                # Import here to avoid circular dependency
                from ciris_engine.logic.adapters.api.routes.agent import store_message_response
                # Store a simple response
                response = f"I received your message: '{msg.content}'. In API mock mode, I cannot process it fully. The answer to 2+2 is 4."
                
                # Store in history
                self.app.state.message_history.append({
                    "message_id": msg.message_id,
                    "author_id": msg.author_id,
                    "content": msg.content,
                    "response": response,
                    "timestamp": msg.timestamp,
                    "channel_id": msg.channel_id
                })
                
                await store_message_response(msg.message_id, response)
            
            self.app.state.on_message = mock_handler
            logger.info("Set up mock message handler for API mode")
        if hasattr(runtime, 'agent_processor') and runtime.agent_processor is not None:
            self.app.state.agent_processor = runtime.agent_processor
            logger.info("Injected agent_processor")
        if hasattr(runtime, 'message_handler') and runtime.message_handler is not None:
            self.app.state.message_handler = runtime.message_handler
            logger.info("Injected message_handler")
        
        # Inject missing services
        if hasattr(runtime, 'shutdown_service') and runtime.shutdown_service is not None:
            self.app.state.shutdown_service = runtime.shutdown_service
            logger.info("Injected shutdown_service")
        if hasattr(runtime, 'initialization_service') and runtime.initialization_service is not None:
            self.app.state.initialization_service = runtime.initialization_service
            logger.info("Injected initialization_service")
        if hasattr(runtime, 'tsdb_consolidation_service') and runtime.tsdb_consolidation_service is not None:
            self.app.state.tsdb_service = runtime.tsdb_consolidation_service
            logger.info("Injected tsdb_service")
        if hasattr(runtime, 'secrets_service') and runtime.secrets_service is not None:
            self.app.state.secrets_service = runtime.secrets_service
            logger.info("Injected secrets_service")
        if hasattr(runtime, 'adaptive_filter_service') and runtime.adaptive_filter_service is not None:
            self.app.state.adaptive_filter = runtime.adaptive_filter_service
            logger.info("Injected adaptive_filter")
        
        # Check for visibility and self_config services
        if hasattr(runtime, 'visibility_service') and runtime.visibility_service is not None:
            self.app.state.visibility_service = runtime.visibility_service
            logger.info("Injected visibility_service")
        if hasattr(runtime, 'self_observation_service') and runtime.self_observation_service is not None:
            self.app.state.self_observation_service = runtime.self_observation_service
            logger.info("Injected self_observation_service")

    async def start(self) -> None:
        """Start the API server."""
        await super().start()
        
        # Start the communication service
        await self.communication.start()
        logger.info("Started API communication service")
        
        # Inject services now that they're initialized
        self._inject_services()
        
        # Start observer
        await self.observer.start()
        
        # Configure uvicorn
        config = uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
            access_log=True
        )
        
        # Create and start server
        self._server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(self._server.serve())
        
        logger.info(
            f"API server starting on http://{self.config.host}:{self.config.port}"
        )
        
        # Wait a moment for server to start
        await asyncio.sleep(1)
    
    async def stop(self) -> None:
        """Stop the API server."""
        logger.info("Stopping API server...")
        
        # Stop communication service
        await self.communication.stop()
        
        # Stop observer
        await self.observer.stop()
        
        # Stop server
        if self._server:
            self._server.should_exit = True
            if self._server_task:
                await self._server_task
        
        await super().stop()
    
    async def health_check(self) -> dict:
        """Check API server health."""
        return {
            "service_name": "API Adapter",
            "status": "healthy" if self._server else "stopped",
            "host": self.config.host,
            "port": self.config.port,
            "endpoints": 35,  # From v1 spec
            "auth_enabled": self.config.auth_enabled,
            "cors_enabled": self.config.cors_enabled
        }
    
    async def run_lifecycle(self, agent_run_task: asyncio.Task) -> None:
        """Run the adapter lifecycle - API runs until agent stops."""
        logger.info("API adapter running lifecycle")
        
        try:
            # Wait for either the agent task or server task to complete
            while not agent_run_task.done():
                # Check if server is still running
                if self._server_task and self._server_task.done():
                    # Server stopped unexpectedly
                    exc = self._server_task.exception()
                    if exc:
                        logger.error(f"API server stopped with error: {exc}")
                        raise exc
                    else:
                        logger.warning("API server stopped unexpectedly")
                        break
                
                # Wait for a short time before checking again
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info("API adapter lifecycle cancelled")
            raise
        except Exception as e:
            logger.error(f"API adapter lifecycle error: {e}")
            raise
        finally:
            logger.info("API adapter lifecycle ending")