"""
Simplified API adapter that acts as a REST interface to runtime services.
Following the pattern of the refactored Discord adapter.
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid

from aiohttp import web

from ciris_engine.protocols.services import CommunicationService
from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage, IncomingMessage
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus
from ciris_engine.schemas.api_schemas_v1 import (
    MessageResponse,
    ServicesResponse, ServiceProvider, RuntimeStatusResponse, 
    RuntimeStatus, ErrorResponse
)
from ciris_engine.persistence import add_correlation

logger = logging.getLogger(__name__)


class APIAdapter(CommunicationService):
    """
    API adapter implementing CommunicationService protocol.
    Provides REST endpoints for interacting with the CIRIS agent.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        bus_manager: Optional[Any] = None,
        service_registry: Optional[Any] = None,
        runtime_control: Optional[Any] = None,
        telemetry_collector: Optional[Any] = None,
        runtime: Optional[Any] = None,
        on_message: Optional[Any] = None
    ) -> None:
        """
        Initialize the API adapter.
        
        Args:
            host: Host to bind the API server to
            port: Port to bind the API server to
            bus_manager: Multi-service sink for routing messages
            service_registry: Service registry for accessing runtime services
            runtime_control: Runtime control service for system management
            telemetry_collector: Telemetry collector for metrics
            runtime: Runtime instance for accessing auth services
        """
        super().__init__(config={"retry": {"global": {"max_retries": 3, "base_delay": 1.0}}})
        
        self.host = host
        self.port = port
        self.bus_manager = bus_manager
        self.service_registry = service_registry
        self.runtime_control = runtime_control
        self.telemetry_collector = telemetry_collector
        self.runtime = runtime
        self.on_message = on_message
        
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._setup_routes()
        
        self._message_queue: List[IncomingMessage] = []
        self._queue_lock = asyncio.Lock()
    
    def _setup_routes(self) -> None:
        """Set up API routes following the agent capabilities philosophy."""
        # Core principle: Expose agent capabilities and observability, not handlers
        
        # Agent Interaction - How to communicate with the agent
        from .api_agent import APIAgentRoutes
        agent_routes = APIAgentRoutes(self.bus_manager, self.on_message)
        agent_routes.register(self.app)
        
        # Memory Observability - View into the agent's graph memory
        from .api_memory import APIMemoryRoutes
        memory_routes = APIMemoryRoutes(self.bus_manager)
        memory_routes.register(self.app)
        
        # Visibility - Windows into agent reasoning and state
        from .api_visibility import APIVisibilityRoutes
        visibility_routes = APIVisibilityRoutes(
            bus_manager=self.bus_manager,
            telemetry_collector=self.telemetry_collector
        )
        visibility_routes.register(self.app)
        
        # Telemetry - System monitoring and observability
        from .api_telemetry import APITelemetryRoutes
        telemetry_routes = APITelemetryRoutes(
            telemetry_collector=self.telemetry_collector,
            service_registry=self.service_registry,
            bus_manager=self.bus_manager
        )
        telemetry_routes.register(self.app)
        
        # Runtime Control - System management (not agent control)
        from .api_runtime_control import APIRuntimeControlRoutes
        runtime_routes = APIRuntimeControlRoutes(
            runtime_control=self.runtime_control,
            service_registry=self.service_registry
        )
        runtime_routes.register(self.app)
        
        # Authentication - WA and OAuth management
        if self.runtime:
            from .api_auth import APIAuthRoutes
            auth_routes = APIAuthRoutes(self.runtime)
            auth_routes.register(self.app)
        
        # Health check endpoint (simple, always available)
        self.app.router.add_get("/v1/health", self._handle_health_check)
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        """
        Send a message to a channel (in API context, this stores the response in the queue).
        
        Args:
            channel_id: The channel/endpoint identifier
            content: The message content
            
        Returns:
            True if message was sent successfully
        """
        correlation_id = str(uuid.uuid4())
        try:
            # In API context, "sending" means making the response available in the queue
            logger.info(f"API response for channel {channel_id}: {content[:100]}...")
            
            # Create a response message and add it to the queue
            response_msg = IncomingMessage(
                message_id=str(uuid.uuid4()),
                author_id="ciris_agent",
                author_name="CIRIS Agent",
                content=content,
                channel_id=channel_id,  # This sets destination_id via alias
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            
            async with self._queue_lock:
                self._message_queue.append(response_msg)
                logger.debug(f"Added response to queue for channel {channel_id}: {response_msg.message_id}")
            
            # Log correlation
            add_correlation(
                ServiceCorrelation(
                    correlation_id=correlation_id,
                    service_type="api",
                    handler_name="APIAdapter",
                    action_type="send_message",
                    request_data={"channel_id": channel_id, "content": content},
                    response_data={"sent": True, "message_id": response_msg.message_id},
                    status=ServiceCorrelationStatus.COMPLETED,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                )
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send API message: {e}")
            return False
    
    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        """
        Fetch messages from a channel (in API context, from the message queue).
        
        Args:
            channel_id: The channel identifier
            limit: Maximum number of messages to fetch
            
        Returns:
            List of fetched messages
        """
        async with self._queue_lock:
            # Filter messages for the specific channel
            channel_messages = [
                FetchedMessage(
                    id=msg.message_id,
                    author_id=msg.author_id,
                    author_name=msg.author_name,
                    content=msg.content,
                    timestamp=msg.timestamp or datetime.now(timezone.utc).isoformat()
                )
                for msg in self._message_queue
                if msg.destination_id == channel_id
            ][-limit:]  # Get last 'limit' messages
            
            return channel_messages
    
    async def _handle_send_message(self, request: web.Request) -> web.Response:
        """Handle incoming message via API."""
        try:
            data = await request.json()
            
            required_fields = ["message_id", "author_id", "author_name", "content"]
            if not all(field in data for field in required_fields):
                return web.json_response(
                    {"error": "Missing required fields", "required": required_fields},
                    status=400
                )
            
            channel_id = data.get("channel_id", "api_default")
            msg = IncomingMessage(
                message_id=data["message_id"],
                author_id=data["author_id"],
                author_name=data["author_name"],
                content=data["content"],
                channel_id=channel_id,
                reference_message_id=data.get("reference_message_id"),
                timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            )
            
            async with self._queue_lock:
                self._message_queue.append(msg)
            
            # Use the callback to handle the message, which will route through observer
            if self.on_message:
                logger.info(f"API adapter routing message {msg.message_id} to observer")
                await self.on_message(msg)
            else:
                logger.warning("No message handler configured for API adapter")
            
            return web.json_response(
                {"status": "accepted", "message_id": msg.message_id},
                status=202
            )
            
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_fetch_messages(self, request: web.Request) -> web.Response:
        """Handle fetching messages for a channel."""
        try:
            channel_id = request.match_info["channel_id"]
            limit = int(request.query.get("limit", 100))
            
            messages = await self.fetch_messages(channel_id, limit)
            
            return web.json_response({
                "channel_id": channel_id,
                "messages": [
                    {
                        "message_id": msg.message_id,
                        "author_id": msg.author_id,
                        "author_name": msg.author_name,
                        "content": msg.content,
                        "timestamp": msg.timestamp,
                    }
                    for msg in messages
                ]
            })
            
        except Exception as e:
            logger.error(f"Error fetching messages: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_health_check(self, request: web.Request) -> web.Response:
        """Handle health check endpoint."""
        health_status: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "services": {}
        }
        
        if self.service_registry:
            try:
                # Get all service types from ServiceType enum
                from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
                for service_type in ServiceType:
                    providers = self.service_registry.get_services_by_type(service_type)
                    if providers:
                        healthy_count = 0
                        for p in providers:
                            try:
                                if hasattr(p, "is_healthy"):
                                    if asyncio.iscoroutinefunction(p.is_healthy):
                                        is_healthy = await p.is_healthy()
                                    else:
                                        is_healthy = p.is_healthy()
                                    if is_healthy:
                                        healthy_count += 1
                                else:
                                    healthy_count += 1  # Assume healthy if no method
                            except Exception:
                                pass  # Count as unhealthy if check fails
                        
                        health_status["services"][service_type.value] = {
                            "available": len(providers),
                            "healthy": healthy_count
                        }
            except Exception as e:
                logger.error(f"Error checking service health: {e}")
                health_status["services_error"] = str(e)
        
        return web.json_response(health_status)
    
    async def _handle_list_services(self, request: web.Request) -> web.Response:
        """Handle listing available services."""
        if not self.service_registry:
            return web.json_response(
                {"error": "Service registry not available"},
                status=503
            )
        
        try:
            # Use get_provider_info which provides detailed service information
            provider_info = self.service_registry.get_provider_info()
            service_providers: Dict[str, List[ServiceProvider]] = {}
            
            # Process handler-specific services
            for handler, services in provider_info.get("handlers", {}).items():
                for service_type, providers in services.items():
                    if service_type not in service_providers:
                        service_providers[service_type] = []
                    for provider in providers:
                        service_providers[service_type].append(ServiceProvider(
                            provider=provider["name"],
                            handler=handler,
                            priority=str(provider["priority"]),
                            capabilities=provider["capabilities"],
                            is_global=False
                        ))
            
            # Process global services
            for service_type, providers in provider_info.get("global_services", {}).items():
                if service_type not in service_providers:
                    service_providers[service_type] = []
                for provider in providers:
                    service_providers[service_type].append(ServiceProvider(
                        provider=provider["name"],
                        handler="global",
                        priority=str(provider["priority"]),
                        capabilities=provider["capabilities"],
                        is_global=True
                    ))
            
            response = ServicesResponse(
                services=service_providers,
                timestamp=datetime.now(timezone.utc)
            )
            
            return web.json_response(response.model_dump(mode='json'))
            
        except Exception as e:
            logger.error(f"Error listing services: {e}", exc_info=True)
            error_response = ErrorResponse(error=str(e))
            return web.json_response(error_response.model_dump(mode='json'), status=500)
    
    async def _handle_runtime_status(self, request: web.Request) -> web.Response:
        """Handle runtime status endpoint."""
        if not self.runtime_control:
            return web.json_response(
                {"error": "Runtime control not available"},
                status=503
            )
        
        try:
            status = await self.runtime_control.get_runtime_status()
            return web.json_response(status)
        except Exception as e:
            logger.error(f"Error getting runtime status: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_runtime_control(self, request: web.Request) -> web.Response:
        """Handle runtime control commands."""
        if not self.runtime_control:
            return web.json_response(
                {"error": "Runtime control not available"},
                status=503
            )
        
        try:
            data = await request.json()
            command = data.get("command")
            params = data.get("params", {})
            
            if not command:
                return web.json_response(
                    {"error": "Missing command"},
                    status=400
                )
            
            result = await self.runtime_control.execute_command(command, params)
            return web.json_response(result)
            
        except Exception as e:
            logger.error(f"Error executing runtime command: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Handle metrics endpoint."""
        if not self.telemetry_collector:
            return web.json_response(
                {"error": "Telemetry collector not available"},
                status=503
            )
        
        try:
            metrics = await self.telemetry_collector.get_current_metrics()
            return web.json_response(metrics)
        except Exception as e:
            logger.error(f"Error getting metrics: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_telemetry_report(self, request: web.Request) -> web.Response:
        """Handle telemetry report endpoint."""
        if not self.telemetry_collector:
            return web.json_response(
                {"error": "Telemetry collector not available"},
                status=503
            )
        
        try:
            report = await self.telemetry_collector.generate_report()
            return web.json_response(report)
        except Exception as e:
            logger.error(f"Error generating telemetry report: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def start(self) -> None:
        """Start the API server."""
        logger.info(f"Starting API server on {self.host}:{self.port}")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"API server started on http://{self.host}:{self.port}")
    
    async def stop(self) -> None:
        """Stop the API server."""
        logger.info("Stopping API server...")
        if self.site:
            await self.site.stop()
            self.site = None
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
        logger.info("API server stopped")
        
        # Give aiohttp time to fully close connections
        # This helps with subprocess exit issues
        await asyncio.sleep(0.1)
    
    async def is_healthy(self) -> bool:
        """Check if the API adapter is healthy."""
        return self.runner is not None and self.site is not None
    
    async def get_capabilities(self) -> List[str]:
        """Return list of capabilities this service supports."""
        capabilities = ["send_message", "fetch_messages", "health_check", "list_services"]
        if self.runtime_control:
            capabilities.extend(["runtime_status", "runtime_control"])
        if self.telemetry_collector:
            capabilities.extend(["metrics", "telemetry_report"])
        return capabilities