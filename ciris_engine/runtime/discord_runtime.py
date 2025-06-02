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
from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.adapters import ToolRegistry
from ciris_engine.action_handlers.tool_handler import ToolHandler
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_tools import CLIToolService

# Import multi-service sink components
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
        self.cli_adapter = CLIAdapter()
        self.cli_tool_service: Optional[CLIToolService] = None
        
        # Create DiscordObserver to handle message processing
        self.discord_observer = DiscordObserver(
            monitored_channel_id=self.monitored_channel_id,
            agent_id=None,  # Will be set during initialization
            multi_service_sink=None  # Will be set during initialization
        )
        
        # Initialize base runtime
        super().__init__(
            profile_name=profile_name,
            io_adapter=self.discord_adapter,
            startup_channel_id=startup_channel_id,
        )
        

        
    async def initialize(self):
        """Initialize Discord-specific components."""
        await super().initialize()

        # Create and assign the Discord client (Bot)
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.discord_adapter.client = self.client  # Assign the client to the adapter


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
        
        # Set up DiscordObserver with proper services after multi_service_sink is available
        if self.discord_observer:
            self.discord_observer.multi_service_sink = self.multi_service_sink
            self.discord_observer.memory_service = self.memory_service  
            self.discord_observer.agent_id = getattr(self, 'agent_id', None)
            # Start the DiscordObserver to handle incoming messages
            await self.discord_observer.start()
            logger.info("DiscordObserver configured and started with runtime services")

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

        # Rebuild dispatcher with correct services
        if self.agent_processor:
            dependencies = getattr(self.agent_processor.thought_processor, 'dependencies', None)
            if dependencies:
                new_dispatcher = await self._build_action_dispatcher(dependencies)
                self.agent_processor.action_dispatcher = new_dispatcher
                logger.info("DiscordRuntime: Action dispatcher rebuilt with correct sinks.")

        # Start Discord-specific services
        await self.cli_adapter.start()
        


    async def _handle_incoming_message(self, msg: IncomingMessage) -> None:
        """Delegate incoming Discord message handling to DiscordObserver."""
        if self.discord_observer:
            await self.discord_observer.handle_incoming_message(msg)
        else:
            logger.warning("No DiscordObserver available to handle incoming message")
        
    async def _build_action_dispatcher(self, dependencies):
        """Build Discord-specific action dispatcher."""
        return build_action_dispatcher(
            service_registry=self.service_registry,
            shutdown_callback=dependencies.shutdown_callback,
            max_rounds=self.app_config.workflow.max_rounds,
            audit_service=self.audit_service,
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
                
                # Register Discord adapter as wise authority service for DeferHandler
                for handler in ["DeferHandler", "SpeakHandler"]:
                    self.service_registry.register(
                        handler=handler,
                        service_type="wise_authority",
                        provider=self.discord_adapter,
                        priority=Priority.HIGH,
                        capabilities=["fetch_guidance", "send_deferral"]
                    )
                logger.info("Registered Discord adapter as wise authority service")

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
        # Stop Discord services
        discord_services: list[Any] = []

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
    
    async def run(self, num_rounds: Optional[int] = None):
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
                self.agent_processor.start_processing(num_rounds=num_rounds)
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

    async def start_interactive_console(self):
        """Discord does not use a local interactive console, so this is a no-op."""
        pass
