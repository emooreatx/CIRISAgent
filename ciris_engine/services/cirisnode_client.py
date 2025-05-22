import logging
from typing import Any, Dict, List, Optional

import httpx

from ciris_engine.services.audit_service import AuditService
from ciris_engine.core.config_manager import get_config
from ciris_engine.core.config_schemas import CIRISNodeConfig
from ciris_engine.core.foundational_schemas import HandlerActionType

logger = logging.getLogger(__name__)


class CIRISNodeClient:
    """Asynchronous client for interacting with CIRISNode."""

    def __init__(self, audit_service: AuditService, base_url: Optional[str] = None) -> None:
        self.audit_service = audit_service
        config = get_config()
        node_cfg: CIRISNodeConfig = getattr(config, "cirisnode", CIRISNodeConfig())
        node_cfg.load_env_vars()
        self.base_url = base_url or node_cfg.base_url
        self._client = httpx.AsyncClient(base_url=self.base_url)

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        resp = await self._client.post(endpoint, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def run_simplebench(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        """Run the simple bench benchmark for the given model."""
        result = await self._post("/simplebench", {"model_id": model_id, "agent_id": agent_id})
        await self.audit_service.log_action(
            HandlerActionType.TOOL,
            {
                "event_type": "cirisnode_test",
                "originator_id": agent_id,
                "event_summary": "simplebench",
                "event_payload": result,
            },
        )
        return result

    async def run_he300(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        """Run the HE-300 benchmark for the given model."""
        result = await self._post("/he300", {"model_id": model_id, "agent_id": agent_id})
        await self.audit_service.log_action(
            HandlerActionType.TOOL,
            {
                "event_type": "cirisnode_test",
                "originator_id": agent_id,
                "event_summary": "he300",
                "event_payload": result,
            },
        )
        return result

    async def run_chaos_tests(self, agent_id: str, scenarios: List[str]) -> List[Dict[str, Any]]:
        """Run chaos test scenarios and return verdicts."""
        result = await self._post("/chaos", {"agent_id": agent_id, "scenarios": scenarios})
        await self.audit_service.log_action(
            HandlerActionType.TOOL,
            {
                "event_type": "cirisnode_test",
                "originator_id": agent_id,
                "event_summary": "chaos",
                "event_payload": result,
            },
        )
        return result

    async def run_wa_service(self, service: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call a WA service on CIRISNode."""
        result = await self._post(f"/wa/{service}", payload)
        await self.audit_service.log_action(
            HandlerActionType.TOOL,
            {
                "event_type": "cirisnode_test",
                "originator_id": payload.get("agent_id", "unknown"),
                "event_summary": "wa",
                "event_payload": result,
            },
        )
        return result

    async def log_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an event payload to CIRISNode for storage."""
        result = await self._post("/events", event_payload)
        await self.audit_service.log_action(
            HandlerActionType.TOOL,
            {
                "event_type": "cirisnode_event",
                "originator_id": event_payload.get("originator_id", "unknown"),
                "event_summary": event_payload.get("event_type", "event"),
                "event_payload": result,
            },
        )
        return result
