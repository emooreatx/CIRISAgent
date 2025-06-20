import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING, cast

import httpx

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry  # Use schema version
from ciris_engine.config.config_manager import get_config
from ciris_engine.schemas.config_schemas_v1 import CIRISNodeConfig
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ServiceType
from ciris_engine.schemas.protocol_schemas_v1 import ActionContext

if TYPE_CHECKING:
    from ciris_engine.protocols.services import AuditService
    from ciris_engine.registries.base import ServiceRegistry


logger = logging.getLogger(__name__)


class CIRISNodeClient(Service):
    """Asynchronous client for interacting with CIRISNode."""

    def __init__(self, service_registry: Optional["ServiceRegistry"] = None, base_url: Optional[str] = None) -> None:
        # Configure retry settings for HTTP operations
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": 3,
                    "base_delay": 1.0,
                    "max_delay": 30.0,  # Shorter max delay for API calls
                },
                "http_request": {
                    "retryable_exceptions": (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError),
                    "non_retryable_exceptions": (httpx.HTTPStatusError,),  # Will be filtered by status code
                }
            }
        }
        super().__init__(config=retry_config)
        
        self.service_registry = service_registry
        self._audit_service: Optional["AuditService"] = None
        config = get_config()
        node_cfg: CIRISNodeConfig = getattr(config, "cirisnode", CIRISNodeConfig())
        node_cfg.load_env_vars()
        self.base_url = base_url or node_cfg.base_url
        self._client = httpx.AsyncClient(base_url=self.base_url)
        self._closed = False

    async def _get_audit_service(self) -> Optional["AuditService"]:
        """Retrieve the audit service from the registry with caching."""
        if self._audit_service is not None:
            return self._audit_service

        if not self.service_registry:
            logger.debug("CIRISNodeClient has no service registry; audit logging disabled")
            return None

        self._audit_service = await self.service_registry.get_service(
            self.__class__.__name__,
            ServiceType.AUDIT,
            required_capabilities=["log_action"],
            fallback_to_global=True,
        )

        if not self._audit_service:
            logger.warning("No audit service available for CIRISNodeClient")
        return self._audit_service

    async def start(self) -> None:
        """Start the client service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the client service and clean up resources."""
        await self._client.aclose()
        await super().stop()
        self._closed = True

    async def close(self) -> None:
        """Alias for stop() for backwards compatibility."""
        await self.stop()

    def is_closed(self) -> bool:
        return self._closed

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        async def _make_request() -> Any:
            resp = await self._client.post(endpoint, json=payload)
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()  # Don't retry 4xx client errors
            resp.raise_for_status()  # Raise for any other errors (will be retried)
            return await resp.json()
            
        return await self.retry_with_backoff(
            _make_request,
            retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException),
            non_retryable_exceptions=(httpx.HTTPStatusError,),
            **self.get_retry_config("http_request")
        )

    async def _get(self, endpoint: str, params: Dict[str, Any]) -> Any:
        async def _make_request() -> Any:
            resp = await self._client.get(endpoint, params=params)
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()  # Don't retry 4xx client errors
            resp.raise_for_status()  # Raise for any other errors (will be retried)
            return await resp.json()
            
        return await self.retry_with_backoff(
            _make_request,
            retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException),
            non_retryable_exceptions=(httpx.HTTPStatusError,),
            **self.get_retry_config("http_request")
        )

    async def _put(self, endpoint: str, payload: Dict[str, Any]) -> Any:
        async def _make_request() -> Any:
            resp = await self._client.put(endpoint, json=payload)
            if 400 <= resp.status_code < 500:
                resp.raise_for_status()  # Don't retry 4xx client errors
            resp.raise_for_status()  # Raise for any other errors (will be retried)
            return await resp.json()
            
        return await self.retry_with_backoff(
            _make_request,
            retryable_exceptions=(httpx.ConnectError, httpx.TimeoutException),
            non_retryable_exceptions=(httpx.HTTPStatusError,),
            **self.get_retry_config("http_request")
        )

    async def run_simplebench(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        """Run the simple bench benchmark for the given model."""
        result = cast(Dict[str, Any], await self._post("/simplebench", {"model_id": model_id, "agent_id": agent_id}))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=agent_id,
                    task_id="simplebench",
                    handler_name="cirisnode_client",
                    parameters={"model_id": model_id, "agent_id": agent_id}
                ),
                outcome=f"SimpleBench completed with accuracy {result.get('accuracy', 'unknown')}"
            )
        return result

    async def run_he300(self, model_id: str, agent_id: str) -> Dict[str, Any]:
        """Run the HE-300 benchmark for the given model."""
        result = cast(Dict[str, Any], await self._post("/he300", {"model_id": model_id, "agent_id": agent_id}))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=agent_id,
                    task_id="he300",
                    handler_name="cirisnode_client",
                    parameters={"model_id": model_id, "agent_id": agent_id}
                ),
                outcome=f"HE-300 completed with {result.get('benchmarks_run', 0)} benchmarks"
            )
        return result

    async def run_chaos_tests(self, agent_id: str, scenarios: List[str]) -> List[Dict[str, Any]]:
        """Run chaos test scenarios and return verdicts."""
        result = cast(List[Dict[str, Any]], await self._post("/chaos", {"agent_id": agent_id, "scenarios": scenarios}))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=agent_id,
                    task_id="chaos_tests",
                    handler_name="cirisnode_client",
                    parameters={"agent_id": agent_id, "scenarios": scenarios}
                ),
                outcome=f"Chaos tests completed: {len(result)} scenarios"
            )
        return result

    async def run_wa_service(self, service: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call a WA service on CIRISNode."""
        result = cast(Dict[str, Any], await self._post(f"/wa/{service}", payload))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=payload.get("agent_id", "unknown"),
                    task_id=f"wa_service_{service}",
                    handler_name="cirisnode_client",
                    parameters=payload
                ),
                outcome=f"WA service {service} completed"
            )
        return result

    async def log_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send an event payload to CIRISNode for storage."""
        result = cast(Dict[str, Any], await self._post("/events", event_payload))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=event_payload.get("originator_id", "unknown"),
                    task_id="log_event",
                    handler_name="cirisnode_client",
                    parameters=event_payload
                ),
                outcome=f"Event logged: {event_payload.get('event_type', 'event')}"
            )
        return result

    async def fetch_benchmark_prompts(
        self,
        benchmark: str,
        model_id: str,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """Retrieve benchmark prompts from CIRISNode."""
        result = cast(List[Dict[str, Any]], await self._get(
            f"/bench/{benchmark}/prompts",
            {"model_id": model_id, "agent_id": agent_id},
        ))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=agent_id,
                    task_id=f"fetch_{benchmark}_prompts",
                    handler_name="cirisnode_client",
                    parameters={"benchmark": benchmark, "model_id": model_id, "agent_id": agent_id}
                ),
                outcome=f"Fetched {len(result)} {benchmark} prompts"
            )
        return result

    async def submit_benchmark_answers(
        self,
        benchmark: str,
        model_id: str,
        agent_id: str,
        answers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Send benchmark answers back to CIRISNode."""
        result = cast(Dict[str, Any], await self._put(
            f"/bench/{benchmark}/answers",
            {"model_id": model_id, "agent_id": agent_id, "answers": answers},
        ))
        audit_service = await self._get_audit_service()
        if audit_service:
            await audit_service.log_action(
                HandlerActionType.TOOL,
                ActionContext(
                    thought_id=agent_id,
                    task_id=f"submit_{benchmark}_answers",
                    handler_name="cirisnode_client",
                    parameters={"benchmark": benchmark, "model_id": model_id, "agent_id": agent_id, "answer_count": len(answers)}
                ),
                outcome=f"Submitted {len(answers)} {benchmark} answers"
            )
        return result
