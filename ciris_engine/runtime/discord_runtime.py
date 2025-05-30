"""
ciris_engine/runtime/discord_runtime.py

Discord-specific runtime implementation with proper service context passing.
"""
import os
import logging
from typing import Optional, Dict, Any

import discord

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter, DiscordEventQueue
from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.adapters import ToolRegistry
from ciris_engine.action_handlers.tool_handler import ToolHandler

# Import multi-service sink components
from ciris_engine.sinks import MultiServiceActionSink, MultiServiceDeferralSink
from ciris_engine.registries.base import ServiceRegistry, Priority
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
        self.message_queue = DiscordEventQueue[IncomingMessage]()
        self.discord_adapter = DiscordAdapter(token, self.message_queue)
        self.monitored_channel_id = monitored_channel_id or os.getenv("DISCORD_CHANNEL_ID")
        self.deferral_channel_id = deferral_channel_id or os.getenv("DISCORD_DEFERRAL_CHANNEL_ID")
        
        # Initialize base runtime
        super().__init__(
            profile_name=profile_name,
            io_adapter=self.discord_adapter,
            startup_channel_id=startup_channel_id,
        )
        
        # Discord-specific services
        self.discord_observer: Optional[DiscordObserver] = None
        self.action_sink: Optional[MultiServiceActionSink] = None
        self.deferral_sink: Optional[MultiServiceDeferralSink] = None
        
    async def initialize(self):
        """Initialize Discord-specific components."""
        await super().initialize()

        # Create and assign the Discord client (Bot)
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.discord_adapter.client = self.client  # Assign the client to the adapter

        # Create action sink using MultiServiceActionSink
        if not self.service_registry:
            logger.error("ServiceRegistry not initialized before creating MultiServiceActionSink.")
            # Potentially raise an error or handle appropriately
            # For now, we'll proceed, but this is a critical dependency
        self.action_sink = MultiServiceActionSink(
            service_registry=self.service_registry,
            fallback_channel_id=self.monitored_channel_id
        )
        
        # Create deferral sink using MultiServiceDeferralSink
        self.deferral_sink = MultiServiceDeferralSink(
            service_registry=self.service_registry,
            default_deferral_channel_id=self.deferral_channel_id
        )
        
        # Create Discord observer with proper context
        self.discord_observer = DiscordObserver(
            on_observe=self._handle_observe_event,  # Use wrapper method
            message_queue=self.message_queue,
            monitored_channel_id=self.monitored_channel_id,
            deferral_sink=self.deferral_sink,
        )
        
        # Register Discord tools with the live client
        tool_registry = ToolRegistry()
        register_discord_tools(tool_registry, self.client)
        ToolHandler.set_tool_registry(tool_registry)

        # Update agent processor services with Discord client
        if self.agent_processor:
            # Update the main services dict
            self.agent_processor.services["discord_service"] = self.client
            self.agent_processor.services["discord_client"] = self.client  # Alternative key
            
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
        await self.discord_observer.start()
        await self.action_sink.start()
        await self.deferral_sink.start()
        
        # Register Discord-specific services in the service registry
        await self._register_discord_services()
        
    async def _handle_observe_event(self, payload: Dict[str, Any]):
        """Wrapper for observe event handling with proper context."""
        # Add discord_service to context for active observations
        context = {
            "discord_service": self.client,
            "default_channel_id": self.monitored_channel_id,
            "agent_id": getattr(self.client, 'user', {}).id if hasattr(self.client, 'user') else None
        }
        # Call the actual handler with enhanced context and return its result
        return await handle_discord_observe_event(
            payload=payload,
            mode="passive",  # Default mode
            context=context
        )
        
    async def _build_action_dispatcher(self, dependencies):
        """Build Discord-specific action dispatcher."""
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_ponder_rounds=self.app_config.workflow.max_ponder_rounds,
            action_sink=self.action_sink,
            memory_service=self.memory_service,
            observer_service=self.discord_observer,
            io_adapter=self.discord_adapter,
            deferral_sink=self.deferral_sink,
        )
        
    async def _register_discord_services(self):
        """Register Discord-specific services in the service registry."""
        if not self.service_registry:
            logger.warning("No service registry available for Discord service registration")
            return
        
        try:
            # Register Discord adapter as communication service
            await self.service_registry.register(
                service_instance=self.discord_adapter,
                service_type='communication',
                priority=1,  # High priority for primary Discord service
                capabilities=['send_message', 'fetch_messages'],
                metadata={
                    'platform': 'discord',
                    'token_configured': bool(self.token),
                    'monitored_channel': self.monitored_channel_id,
                    'deferral_channel': self.deferral_channel_id
                }
            )
            
            # Register Discord client as a raw Discord service (for legacy compatibility)
            if self.client:
                await self.service_registry.register(
                    service_instance=self.client,
                    service_type='discord_client',
                    priority=1,
                    capabilities=['raw_discord_access'],
                    metadata={
                        'type': 'discord.Client',
                        'ready': not self.client.is_closed() if hasattr(self.client, 'is_closed') else True
                    }
                )
            
            # Register Discord observer if it exists
            if self.discord_observer:
                await self.service_registry.register(
                    service_instance=self.discord_observer,
                    service_type='observer',
                    priority=1,
                    capabilities=['observe_messages', 'monitor_channel'],
                    metadata={
                        'platform': 'discord',
                        'monitored_channel': self.monitored_channel_id
                    }
                )
            
            logger.info("Successfully registered Discord services in service registry")
            
        except Exception as e:
            logger.error(f"Failed to register Discord services: {e}", exc_info=True)

    async def shutdown(self):
        """Shutdown Discord-specific components."""
        # Stop Discord services
        discord_services = [
            self.discord_observer,
            self.action_sink,
            self.deferral_sink,
        ]
        
        for service in discord_services:
            if service:
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service.__class__.__name__}: {e}")
                    
        # Call parent shutdown
        await super().shutdown()