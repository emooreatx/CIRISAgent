import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage

from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

from ciris_engine.protocols.services import (
    CommunicationService,
    WiseAuthorityService,
    ToolService,
    MemoryService,
    AuditService,
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType


class APICommunicationService(CommunicationService):
    """API-based communication service implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.responses: Dict[str, Any] = {}  # response_id -> response_data
        self.channel_messages: Dict[str, List[Dict[str, Any]]] = {}  # channel_id -> list of messages

    async def start(self) -> None:
        """Start the API communication service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the API communication service."""
        await super().stop()

    async def send_message(self, channel_id: str, content: str) -> bool:
        response_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if channel_id not in self.channel_messages:
            self.channel_messages[channel_id] = []
            
        message = {
            "response_id": response_id,
            "content": content,
            "timestamp": timestamp,
            "channel_id": channel_id
        }
        
        self.channel_messages[channel_id].append(message)
        self.responses[response_id] = message
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        if channel_id not in self.channel_messages:
            return []
        
        messages = self.channel_messages[channel_id][-limit:]
        return [
            FetchedMessage(
                message_id=msg["response_id"],
                author_id="api_system",
                author_name="API System",
                content=msg["content"],
                timestamp=msg["timestamp"],
                channel_id=channel_id
            )
            for msg in messages
        ]


class APIWiseAuthorityService(WiseAuthorityService):
    """API-based wise authority service implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.deferrals: List[Dict[str, Any]] = []

    async def start(self) -> None:
        """Start the API wise authority service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the API wise authority service."""
        await super().stop()

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        return f"API guidance for context: {context.get('summary', 'No context')}"

    async def send_deferral(self, thought_id: str, reason: str, context: Optional[Dict[str, Any]] = None) -> bool:
        deferral = {
            "thought_id": thought_id,
            "reason": reason,
            "context": context or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.deferrals.append(deferral)
        return True


class APIToolService(ToolService):
    """API-based tool service implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.tool_results: Dict[str, Any] = {}
        self.tools: Dict[str, Any] = {"echo": lambda args: {"result": args}}

    async def start(self) -> None:
        """Start the API tool service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the API tool service."""
        await super().stop()

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        correlation_id = str(uuid.uuid4())
        
        if tool_name in self.tools:
            result = self.tools[tool_name](parameters)
            self.tool_results[correlation_id] = result
            return {"correlation_id": correlation_id, "result": result}
        else:
            error = {"error": f"Tool '{tool_name}' not found"}
            self.tool_results[correlation_id] = error
            return {"correlation_id": correlation_id, **error}

    async def get_available_tools(self) -> List[str]:
        return list(self.tools.keys())

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        return self.tool_results.get(correlation_id)


class APIMemoryService(MemoryService):
    """API-based memory service implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.memory: Dict[str, Dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the API memory service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the API memory service."""
        await super().stop()

    async def memorize(self, node: GraphNode) -> MemoryOpResult:
        try:
            self.memory[node.id] = {
                "id": node.id,
                "type": node.type,
                "scope": node.scope,
                "attributes": node.attributes,
                "version": node.version,
                "updated_by": node.updated_by,
                "updated_at": node.updated_at,
            }
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def recall(self, node: GraphNode) -> MemoryOpResult:
        try:
            data = self.memory.get(node.id)
            return MemoryOpResult(status=MemoryOpStatus.OK, data=data)
        except Exception as e:
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def forget(self, node: GraphNode) -> MemoryOpResult:
        try:
            if node.id in self.memory:
                del self.memory[node.id]
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))


class APIAuditService(AuditService):
    """API-based audit service implementation."""

    def __init__(self) -> None:
        super().__init__()
        self.audit_logs: List[Dict[str, Any]] = []
        self.guardrail_logs: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    async def start(self) -> None:
        """Start the API audit service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the API audit service."""
        await super().stop()

    async def log_action(self, action_type: HandlerActionType, context: Dict[str, Any], outcome: Optional[str] = None) -> bool:
        """Log an action for audit purposes."""
        try:
            audit_entry = {
                "id": str(uuid.uuid4()),
                "action_type": action_type.value if hasattr(action_type, 'value') else str(action_type),
                "context": context,
                "outcome": outcome,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.audit_logs.append(audit_entry)
            return True
        except Exception:
            return False

    async def log_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log a general event."""
        event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "event_data": event_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.events.append(event)

    async def log_guardrail_event(self, guardrail_name: str, action_type: str, result: Dict[str, Any]) -> None:
        """Log guardrail check events."""
        guardrail_entry = {
            "id": str(uuid.uuid4()),
            "guardrail_name": guardrail_name,
            "action_type": action_type,
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.guardrail_logs.append(guardrail_entry)

    async def get_audit_trail(self, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit trail for an entity."""
        # Filter logs by entity_id in context and return most recent
        matching_logs = [
            log for log in self.audit_logs 
            if log.get("context", {}).get("entity_id") == entity_id
        ]
        return matching_logs[-limit:] if matching_logs else []