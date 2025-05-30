import json
import logging
from typing import Any, Dict, Optional
from ciris_engine.ports import DeferralSink
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.protocols.services import CommunicationService

logger = logging.getLogger(__name__)

def _truncate_discord_message(message: str, limit: int = 1900) -> str:
    return message if len(message) <= limit else message[:limit-3] + "..."

class DiscordDeferralSink(DeferralSink):
    """Send deferral reports via Discord using service registry for communication."""
    def __init__(self, adapter: Optional[DiscordAdapter] = None, deferral_channel_id: Optional[str] = None, 
                 service_registry: Optional[Any] = None, max_queue_size: int = 500):
        super().__init__(max_queue_size=max_queue_size, service_registry=service_registry)
        # Backward compatibility - keep direct adapter access
        self.adapter = adapter
        self.client = adapter.client if adapter else None
        self.deferral_channel_id = int(deferral_channel_id) if deferral_channel_id else None

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_deferral(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        """Send deferral via service registry communication service, with fallback to direct adapter"""
        if not self.deferral_channel_id:
            logger.warning("DiscordDeferralSink: deferral channel not configured")
            return
        
        # Try to get communication service from registry first
        comm_service = await self.get_service('communication', required_capabilities=['send_message'])
        
        if comm_service:
            success = await self._send_via_service(comm_service, task_id, thought_id, reason, package)
            if success:
                return
            else:
                logger.warning("Failed to send deferral via service registry, falling back to direct adapter")
        
        # Fallback to direct adapter method
        await self._send_via_adapter(task_id, thought_id, reason, package)
    
    async def _send_via_service(self, comm_service: CommunicationService, task_id: str, 
                               thought_id: str, reason: str, package: Dict[str, Any]) -> bool:
        """Send deferral using communication service from registry"""
        try:
            report = self._format_deferral_report(task_id, thought_id, reason, package)
            return await comm_service.send_message(str(self.deferral_channel_id), report)
        except Exception as e:
            logger.error(f"Error sending deferral via communication service: {e}")
            return False
    
    async def _send_via_adapter(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        """Fallback method using direct adapter access"""
        if not self.client:
            logger.error("No Discord client available for fallback")
            return
            
        # Wait for the client to be ready
        if hasattr(self.client, 'wait_until_ready'):
            await self.client.wait_until_ready()
        channel = self.client.get_channel(self.deferral_channel_id)
        if channel is None:
            channel = await self.client.fetch_channel(self.deferral_channel_id)
        if channel is None:
            logger.error("DiscordDeferralSink: cannot access deferral channel %s", self.deferral_channel_id)
            return
        
        report = self._format_deferral_report(task_id, thought_id, reason, package)
        await channel.send(_truncate_discord_message(report))
    
    def _format_deferral_report(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> str:
        """Format deferral report message"""
        if "metadata" in package and "user_nick" in package:
            return (
                f"**Memory Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**User:** {package.get('user_nick')} Channel: {package.get('channel')}\n"
                f"**Reason:** {reason}\n"
                f"**Metadata:** ```json\n{json.dumps(package.get('metadata'), indent=2)}\n```"
            )
        else:
            return (
                f"**Deferral Report**\n"
                f"**Task ID:** `{task_id}`\n"
                f"**Deferred Thought ID:** `{thought_id}`\n"
                f"**Reason:** {reason}\n"
                f"**Deferral Package:** ```json\n{json.dumps(package, indent=2)}\n```"
            )
