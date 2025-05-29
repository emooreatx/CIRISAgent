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
from ciris_engine.adapters.discord.discord_event_queue import DiscordEventQueue
from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.services.discord_deferral_sink import DiscordDeferralSink
from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.ports import ActionSink
from ciris_engine.services.tool_registry import ToolRegistry
from ciris_engine.action_handlers.tool_handler import ToolHandler

logger = logging.getLogger(__name__)


class DiscordActionSink(ActionSink):
    """Discord implementation of ActionSink."""
    
    def __init__(self, discord_adapter: DiscordAdapter):
        self.adapter = discord_adapter
        
    async def start(self) -> None:
        pass
        
    async def stop(self) -> None:
        pass
        
    async def send_message(self, channel_id: str, content: str) -> None:
        await self.adapter.send_output(channel_id, content)
        
    async def run_tool(self, name: str, args: Dict[str, Any]) -> Any:
        # Tool execution is handled by the ToolHandler and ToolRegistry
        logger.info(f"DiscordActionSink: Tool '{name}' execution requested with args: {args}")
        return None


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
        self.action_sink: Optional[DiscordActionSink] = None
        self.deferral_sink: Optional[DiscordDeferralSink] = None
        
    async def initialize(self):
        """Initialize Discord-specific components."""
        await super().initialize()

        # Create and assign the Discord client (Bot)
        intents = discord.Intents.all()
        self.client = discord.Client(intents=intents)
        self.discord_adapter.client = self.client  # Assign the client to the adapter

        # Create action sink
        self.action_sink = DiscordActionSink(self.discord_adapter)
        
        # Create deferral sink
        self.deferral_sink = DiscordDeferralSink(
            self.discord_adapter,
            self.deferral_channel_id
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
        if self.agent_processor:
            ponder_manager = getattr(self.agent_processor.thought_processor, 'ponder_manager', None)
            logger.info(f"DiscordRuntime: Rebuilding dispatcher with action_sink: {self.action_sink}")
            new_dispatcher = await self._build_action_dispatcher(ponder_manager)
            self.agent_processor.action_dispatcher = new_dispatcher
            logger.info("DiscordRuntime: Action dispatcher rebuilt with correct sinks.")

        # Start Discord-specific services
        await self.discord_observer.start()
        await self.action_sink.start()
        await self.deferral_sink.start()
        
    async def _handle_observe_event(self, payload: Dict[str, Any]) -> None:
        """Wrapper for observe event handling with proper context."""
        # Add discord_service to context for active observations
        context = {
            "discord_service": self.client,
            "default_channel_id": self.monitored_channel_id,
            "agent_id": getattr(self.client, 'user', {}).id if hasattr(self.client, 'user') else None
        }
        
        # Call the actual handler with enhanced context
        await handle_discord_observe_event(
            payload=payload,
            mode="passive",  # Default mode
            context=context
        )
        
    async def _build_action_dispatcher(self, ponder_manager):
        """Build Discord-specific action dispatcher."""
        return build_action_dispatcher(
            audit_service=self.audit_service,
            ponder_manager=ponder_manager,
            action_sink=self.action_sink,
            memory_service=self.memory_service,
            observer_service=self.discord_observer,
            io_adapter=self.discord_adapter,
            deferral_sink=self.deferral_sink,
        )
        
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