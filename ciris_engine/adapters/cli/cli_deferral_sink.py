import logging
from typing import Any, Dict, Optional
from ciris_engine.ports import DeferralSink
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.protocols.services import CommunicationService

logger = logging.getLogger(__name__)

def _truncate_cli_message(message: str, limit: int = 1900) -> str:
    return message if len(message) <= limit else message[:limit-3] + "..."

class CLIDeferralSink(DeferralSink):
    """Send deferral reports via CLI using service registry for communication."""
    def __init__(self, adapter: Optional[CLIAdapter] = None, deferral_channel_id: Optional[str] = None,
                 service_registry: Optional[Any] = None, max_queue_size: int = 500):
        super().__init__(max_queue_size=max_queue_size, service_registry=service_registry)
        # Backward compatibility - keep direct adapter access
        self.adapter = adapter
        self.client = adapter.client if adapter else None
        self.deferral_channel_id = deferral_channel_id

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_deferral(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        """Send deferral via service registry communication service, with fallback to CLI output"""
        # Try to get communication service from registry first
        comm_service = await self.get_service('communication', required_capabilities=['send_message'])
        
        if comm_service and self.deferral_channel_id:
            success = await self._send_via_service(comm_service, task_id, thought_id, reason, package)
            if success:
                return
            else:
                logger.warning("Failed to send deferral via service registry, falling back to CLI output")
        
        # Fallback to CLI output
        await self._send_via_cli(task_id, thought_id, reason, package)
    
    async def _send_via_service(self, comm_service: CommunicationService, task_id: str, 
                               thought_id: str, reason: str, package: Dict[str, Any]) -> bool:
        """Send deferral using communication service from registry"""
        try:
            report = self._format_deferral_report(task_id, thought_id, reason, package)
            return await comm_service.send_message(self.deferral_channel_id, report)
        except Exception as e:
            logger.error(f"Error sending deferral via communication service: {e}")
            return False
    
    async def _send_via_cli(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        """Fallback method using CLI output"""
        report = self._format_deferral_report(task_id, thought_id, reason, package)
        print(_truncate_cli_message(report))
    
    def _format_deferral_report(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> str:
        """Format deferral report message"""
        return f"[CLI DEFERRAL] Task: {task_id}, Thought: {thought_id}, Reason: {reason}, Package: {package}"
