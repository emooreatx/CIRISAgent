import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

from ciris_engine.schemas.foundational_schemas_v1 import FetchedMessage

from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
)
from ciris_engine import persistence

from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService, MemoryService

class APIAdapter(CommunicationService, WiseAuthorityService, ToolService, MemoryService):
    """Adapter for HTTP API communication, WA, tools, and memory interactions."""

    def __init__(self):
        self.responses: Dict[str, Any] = {}  # response_id -> response_data
        self.channel_messages: Dict[str, List[Dict[str, Any]]] = {}  # channel_id -> list of messages
        self.tool_results: Dict[str, Any] = {}
        self.memory: Dict[str, Dict[str, Any]] = {}
        self.tools: Dict[str, Any] = {"echo": lambda args: {"result": args}}

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send_message(self, channel_id: str, content: str) -> bool:
        response_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        response_data = {
            "channel_id": channel_id,
            "content": content,
            "timestamp": timestamp,
        }
        
        # Store by response ID (for compatibility)
        self.responses[response_id] = response_data
        
        # Store by channel ID for easy retrieval
        if channel_id not in self.channel_messages:
            self.channel_messages[channel_id] = []
        
        self.channel_messages[channel_id].append({
            "id": response_id,
            "content": content,
            "author_id": "ciris_agent",
            "timestamp": timestamp,
        })
        
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=response_id,
                service_type="api",
                handler_name="APIAdapter",
                action_type="send_message",
                request_data={"channel_id": channel_id, "content": content},
                response_data=response_data,
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        return True

    async def fetch_messages(self, channel_id: str, limit: int = 100) -> List[FetchedMessage]:
        return []

    async def fetch_guidance(self, context: Dict[str, Any]) -> Optional[str]:
        correlation_id = str(uuid.uuid4())
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=correlation_id,
                service_type="api",
                handler_name="APIAdapter",
                action_type="fetch_guidance",
                request_data=context,
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
            )
        )
        return None

    async def send_deferral(self, thought_id: str, reason: str) -> bool:
        self.responses[f"deferral_{thought_id}"] = {
            "type": "deferral",
            "thought_id": thought_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }
        persistence.add_correlation(
            ServiceCorrelation(
                correlation_id=f"deferral_{thought_id}",
                service_type="api",
                handler_name="APIAdapter",
                action_type="send_deferral",
                request_data={"thought_id": thought_id, "reason": reason},
                response_data=self.responses[f"deferral_{thought_id}"],
                status=ServiceCorrelationStatus.COMPLETED,
                created_at=self.responses[f"deferral_{thought_id}"]["timestamp"],
                updated_at=self.responses[f"deferral_{thought_id}"]["timestamp"],
            )
        )
        return True

    # --- ToolService ---
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name in self.tools:
            result = self.tools[tool_name](parameters)
            correlation_id = str(uuid.uuid4())
            self.tool_results[correlation_id] = result
            return {"correlation_id": correlation_id, **result}
        return {"error": f"Tool '{tool_name}' not found"}

    async def get_available_tools(self) -> List[str]:
        return list(self.tools.keys())

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        return self.tool_results.get(correlation_id)

    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        return True

    # --- MemoryService ---
    async def memorize(self, node):
        self.memory[node.id] = node.__dict__
        return True

    async def recall(self, node):
        return self.memory.get(node.id)

    async def forget(self, node):
        return self.memory.pop(node.id, None) is not None

    async def search_memories(self, query: str, scope: str = "default", limit: int = 10) -> List[Dict[str, Any]]:
        return [v for v in self.memory.values() if query in str(v)]
