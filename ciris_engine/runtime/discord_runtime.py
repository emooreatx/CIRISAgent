"""
ciris_engine/runtime/discord_runtime.py

Discord-specific runtime implementation with proper service context passing.
"""
import os
import logging
from typing import Optional, Dict, Any
import asyncio

import discord

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.adapters import ToolRegistry
from ciris_engine.action_handlers.tool_handler import ToolHandler
from ciris_engine.adapters.cli.cli_event_queues import CLIEventQueue
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_tools import CLIToolService

# Import multi-service sink components
from ciris_engine.sinks import MultiServiceActionSink
from ciris_engine.registries.base import Priority
from ciris_engine.adapters import CIRISNodeClient

logger = logging.getLogger(__name__)


class DiscordRuntime(CIRISRuntime):
    """Discord-specific runtime with proper event handling."""
    
    def __init__(
        self,
        token: str,
        profile_name: str = "default",
        startup_channel_id: Optional[str] = None,
        monitored_channel_id: Optional[str] = None,
        deferral_channel_id: Optional[str] = None,
    ):
        # Create Discord components
        self.token = token
        self.discord_adapter = DiscordAdapter(token, on_message=self._handle_incoming_message)
        self.monitored_channel_id = monitored_channel_id or os.getenv("DISCORD_CHANNEL_ID")
        self.deferral_channel_id = deferral_channel_id or os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")

        # CLI fallback components
        self.cli_adapter = CLIAdapter(CLIEventQueue[IncomingMessage](), interactive=False)
        self.cli_tool_service: Optional[CLIToolService] = None
        
        # Initialize base runtime
        super().__init__(
            profile_name=profile_name,
            io_adapter=self.discord_adapter,
            startup_channel_id=startup_channel_id,
        )
        
        # Discord-specific services
        self.action_sink: Optional[MultiServiceActionSink] = None
        
    async def initialize(self):
        """Initialize Discord-specific components."""
        await super().initialize()

        # Create and assign the Discord client (Bot)
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.discord_adapter.client = self.client  # Assign the client to the adapter

        # Create action sink using MultiServiceActionSink
        if not self.service_registry:
            logger.error("Service registry not initialized before creating MultiServiceActionSink.")
            # Potentially raise an error or handle appropriately
            # For now, we'll proceed, but this is a critical dependency
        self.action_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            fallback_channel_id=self.monitored_channel_id
        )

        # CLI fallback tool service
        self.cli_tool_service = CLIToolService()
        
        # Register Discord tools with the live client
        tool_registry = ToolRegistry()
        register_discord_tools(tool_registry, self.client)
        
        # Set the tool registry on the Discord adapter (which implements ToolService)
        if hasattr(self.discord_adapter, 'tool_registry'):
            self.discord_adapter.tool_registry = tool_registry
        
        # Register Discord adapter as tool service in the service registry
        if self.service_registry and self.discord_adapter:
            self.service_registry.register(
                handler="ToolHandler",
                service_type="tool",
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                capabilities=["execute_tool", "get_tool_result", "get_available_tools", "validate_parameters"]
            )

        # Register Discord-specific services before dispatcher is built
        await self._register_discord_services()

        # Update agent processor services with Discord client
        if self.agent_processor:
            # Update the main services dict
            self.agent_processor.services["discord_service"] = self.client
            
            # Set discord_service on all processors for context passing
            processors = [
                self.agent_processor.wakeup_processor,
                self.agent_processor.work_processor,
                self.agent_processor.play_processor,
                self.agent_processor.solitude_processor
            ]
            
            for processor in processors:
                if processor:
                    processor.discord_service = self.client
                    processor.services = self.agent_processor.services  # Share services dict
                    logger.debug(f"Set discord_service on {processor.__class__.__name__}")

        # Rebuild dispatcher with correct sinks and services
        # Rebuild action dispatcher with proper sinks after action_sink is created
        if self.agent_processor:
            dependencies = getattr(self.agent_processor.thought_processor, 'dependencies', None)
            if dependencies:
                # Update the action_sink in dependencies
                dependencies.action_sink = self.action_sink
            logger.info(f"DiscordRuntime: Rebuilding dispatcher with action_sink: {self.action_sink}")
            new_dispatcher = await self._build_action_dispatcher(dependencies)
            self.agent_processor.action_dispatcher = new_dispatcher
            logger.info("DiscordRuntime: Action dispatcher rebuilt with correct sinks.")

        # Start Discord-specific services
        await self.cli_adapter.start()
        
        # Start sinks as background tasks since they contain infinite loops
        self.action_sink_task = asyncio.create_task(self.action_sink.start())


    async def _handle_incoming_message(self, msg: IncomingMessage) -> None:
        """Convert an incoming Discord message to an observation payload."""
        payload = {
            "type": "OBSERVATION",
            "message_id": msg.message_id,
            "content": msg.content,
            "context": {
                "origin_service": "discord",
                "author_id": msg.author_id,
                "author_name": msg.author_name,
                "channel_id": msg.channel_id,
            },
            "task_description": (
                f"Observed user @{msg.author_name} (ID: {msg.author_id}) in channel #{msg.channel_id} "
                f"(Msg ID: {msg.message_id}) say: '{msg.content}'. Evaluate and decide on the appropriate course of action."
            ),
        }
        await self._handle_observe_event(payload)

    async def _handle_observe_event(self, payload: Dict[str, Any]):
        """Forward observation payload through the multi service sink."""
        logger.debug("Discord runtime received observe event: %s", payload)

        sink = self.action_sink or self.multi_service_sink
        if not sink:
            logger.warning("No action sink available for observe payload")
            return None

        channel_id = payload.get("context", {}).get("channel_id", self.monitored_channel_id)
        content = payload.get("content", "")
        metadata = {"observer_payload": payload}

        message = IncomingMessage(
            message_id=str(payload.get("message_id")),
            author_id=str(payload.get("context", {}).get("author_id", "unknown")),
            author_name=str(payload.get("context", {}).get("author_name", "unknown")),
            content=content,
            channel_id=str(channel_id),
        )

        await sink.observe_message("ObserveHandler", message, metadata)
        return None
        
    async def _build_action_dispatcher(self, dependencies):
        """Build Discord-specific action dispatcher."""
        return build_action_dispatcher(
            service_registry=self.service_registry,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=self.app_config.workflow.max_rounds,
            audit_service=self.audit_service,
            action_sink=self.action_sink,
            memory_service=self.memory_service,
            io_adapter=self.discord_adapter,
        )
        
    async def _register_discord_services(self):
        """Register Discord-specific services in the service registry."""
        if not self.service_registry:
            logger.warning("No service registry available for Discord service registration")
            return
        
        try:
            # Register Discord adapter as communication service
            if self.discord_adapter:
                # Register for all handlers that need communication
                for handler in ["SpeakHandler", "ObserveHandler", "ToolHandler"]:
                    self.service_registry.register(
                        handler=handler,
                        service_type="communication",
                        provider=self.discord_adapter,
                        priority=Priority.HIGH,
                        capabilities=["send_message", "fetch_messages"]
                    )
                logger.info("Registered Discord adapter as communication service")

            # Register CLI adapter as fallback communication service
            if self.cli_adapter:
                for handler in ["SpeakHandler", "ObserveHandler", "ToolHandler"]:
                    self.service_registry.register(
                        handler=handler,
                        service_type="communication",
                        provider=self.cli_adapter,
                        priority=Priority.NORMAL,
                        capabilities=["send_message"]
                    )
                logger.info("Registered CLI adapter as fallback communication service")
            

            # Register CLI tool service as fallback
            if self.cli_tool_service:
                self.service_registry.register(
                    handler="ToolHandler",
                    service_type="tool",
                    provider=self.cli_tool_service,
                    priority=Priority.NORMAL,
                    capabilities=["execute_tool", "get_tool_result"]
                )
                logger.info("Registered CLI tool service as fallback")
            
            # Register CIRISNode as WA service if available
            if hasattr(self, 'cirisnode_client') and self.cirisnode_client:
                for handler in ["DeferHandler", "SpeakHandler"]:
                    self.service_registry.register(
                        handler=handler,
                        service_type="wise_authority",
                        provider=self.cirisnode_client,
                        priority=Priority.NORMAL,
                        capabilities=["request_guidance", "submit_deferral"]
                    )
                logger.info("Registered CIRISNode as wise authority service")
            
            logger.info("Successfully registered all Discord services in service registry")
            
        except Exception as e:
            logger.error(f"Failed to register Discord services: {e}", exc_info=True)

    async def shutdown(self):
        """Shutdown Discord-specific components."""
        # Cancel sink background tasks
        if hasattr(self, 'action_sink_task') and self.action_sink_task:
            self.action_sink_task.cancel()
            try:
                await self.action_sink_task
            except asyncio.CancelledError:
                pass
        
        
        # Stop Discord services
        discord_services = [
            self.action_sink,
        ]
        
        for service in discord_services:
            if service:
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service.__class__.__name__}: {e}")

        if self.cli_adapter:
            try:
                await self.cli_adapter.stop()
            except Exception as e:
                logger.error(f"Error stopping {self.cli_adapter.__class__.__name__}: {e}")
                    
        # Call parent shutdown
        await super().shutdown()
    
    async def run(self, max_rounds: Optional[int] = None):
        """Run the Discord runtime with proper client connection."""
        if not self._initialized:
            await self.initialize()
            
        # Initialize task variables to None
        discord_task = None
        processing_task = None
        sink_task = None
            
        try:
            # Start multi-service sink processing as background task
            if self.multi_service_sink:
                sink_task = asyncio.create_task(self.multi_service_sink.start())
                logger.info("Started multi-service sink as background task")
            
            # Start IO adapter (this doesn't start Discord client yet)
            await self.io_adapter.start()
            logger.info("Started IO adapter")
            
            # Attach event handlers to Discord client
            self.discord_adapter.attach_to_client(self.client)
            logger.info("Attached Discord event handlers")
            
            # Start Discord client connection in background
            logger.info("Starting Discord client connection...")
            discord_task = asyncio.create_task(self.client.start(self.token))
            
            # Wait for Discord to be ready
            logger.info("Waiting for Discord client to be ready...")
            ready_timeout = 30  # seconds
            start_time = asyncio.get_event_loop().time()
            
            while not self.client.is_ready():
                await asyncio.sleep(0.5)
                if asyncio.get_event_loop().time() - start_time > ready_timeout:
                    logger.error("Discord client failed to become ready within timeout")
                    raise RuntimeError("Discord client connection timeout")
            
            logger.info(f"Discord client ready! User: {self.client.user}")
            
            # NOW start agent processing - this is the key part that triggers WAKEUP
            logger.info("Starting agent processing with WAKEUP sequence...")
            processing_task = asyncio.create_task(
                self.agent_processor.start_processing(num_rounds=max_rounds)
            )
            
            # Wait for either task to complete or error
            done, pending = await asyncio.wait(
                [discord_task, processing_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Check which task completed and why
            for task in done:
                if task.exception():
                    logger.error(f"Task failed with exception: {task.exception()}")
                    raise task.exception()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        except Exception as e:
            logger.error(f"Runtime error: {e}", exc_info=True)
        finally:
            # Cancel any pending tasks
            for task in [discord_task, processing_task, sink_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Close Discord client properly
            if self.client and not self.client.is_closed():
                await self.client.close()
                
            await self.shutdown()
