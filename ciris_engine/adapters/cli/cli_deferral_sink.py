import logging
from typing import Any, Dict, Optional
from ciris_engine.ports import DeferralSink
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter

logger = logging.getLogger(__name__)

def _truncate_cli_message(message: str, limit: int = 1900) -> str:
    return message if len(message) <= limit else message[:limit-3] + "..."

class CLIDeferralSink(DeferralSink):
    """Send deferral reports via CLI (stdout or event queue)."""
    def __init__(self, adapter: CLIAdapter, deferral_channel_id: Optional[str]):
        self.adapter = adapter
        self.client = adapter.client
        self.deferral_channel_id = deferral_channel_id
    async def start(self):
        pass
    async def stop(self):
        pass
    async def send_deferral(self, task_id: str, thought_id: str, reason: str, package: Dict[str, Any]) -> None:
        report = f"[CLI DEFERRAL] Task: {task_id}, Thought: {thought_id}, Reason: {reason}, Package: {package}"
        print(_truncate_cli_message(report))
