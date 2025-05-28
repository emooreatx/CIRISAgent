from __future__ import annotations
import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, Any
import asyncio

import networkx as nx

from ciris_engine.schemas.graph_schemas_v1 import (
    GraphScope,
    GraphNode,
    NodeType,
    GraphEdge,
)
from ciris_engine.schemas.foundational_schemas_v1 import CaseInsensitiveEnum, TaskStatus
from ..services.base import Service
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MemoryOpStatus(CaseInsensitiveEnum):
    OK = "ok"
    DEFERRED = "deferred"
    DENIED = "denied"


class MemoryOpResult(BaseModel):
    status: MemoryOpStatus
    reason: Optional[str] = None
    data: Optional[Any] = None


class CIRISLocalGraph(Service):
    """Local graph storage split across three scopes."""

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.storage_path = Path(storage_path or "memory_graph.pkl")
        self._graphs: Dict[GraphScope, nx.DiGraph] = {
            GraphScope.LOCAL: nx.DiGraph(),
            GraphScope.IDENTITY: nx.DiGraph(),
            GraphScope.ENVIRONMENT: nx.DiGraph(),
        }
        if self.storage_path.exists():
            self._load()

    # backward-compat graph property used in tests
    @property
    def graph(self) -> nx.DiGraph:
        return self._graphs[GraphScope.LOCAL]

    def _load(self) -> None:
        try:
            with self.storage_path.open("rb") as f:
                data = pickle.load(f)
            for scope in self._graphs:
                g = data.get(scope.value)
                if isinstance(g, nx.DiGraph):
                    self._graphs[scope] = g
        except Exception as exc:
            logger.warning("Failed loading graphs: %s", exc)

    def _persist(self) -> None:
        to_store = {scope.value: g for scope, g in self._graphs.items()}
        try:
            with self.storage_path.open("wb") as f:
                pickle.dump(to_store, f)
        except Exception as exc:
            logger.warning("Failed persisting graphs: %s", exc)

    async def start(self):
        await super().start()
        if self.storage_path.exists():
            self._load()

    async def stop(self):
        self._persist()
        await super().stop()

    async def memorize(self, node: GraphNode, *args, **kwargs) -> MemoryOpResult:
        """Store a node. Older call signatures are supported for compatibility."""
        if not isinstance(node, GraphNode):
            # Legacy: memorize(user_nick, channel, metadata, channel_metadata=None, is_correction=False)
            user_nick = node
            channel = args[0] if len(args) > 0 else None
            metadata = args[1] if len(args) > 1 else {}
            scope = GraphScope.LOCAL
            attributes = metadata or {}
            node = GraphNode(id=str(user_nick), type=NodeType.USER, scope=scope, attributes=attributes)
        g = self._graphs[node.scope]
        g.add_node(node.id, **node.attributes)
        await asyncio.to_thread(self._persist)
        return MemoryOpResult(status=MemoryOpStatus.OK)

    async def remember(self, node_id: str, scope: GraphScope) -> MemoryOpResult:
        g = self._graphs[scope]
        if g.has_node(node_id):
            return MemoryOpResult(
                status=MemoryOpStatus.OK, data=dict(g.nodes[node_id])
            )
        return MemoryOpResult(status=MemoryOpStatus.OK, data=None)

    async def forget(self, node_id: str, scope: GraphScope) -> MemoryOpResult:
        g = self._graphs[scope]
        if g.has_node(node_id):
            g.remove_node(node_id)
            await asyncio.to_thread(self._persist)
        return MemoryOpResult(status=MemoryOpStatus.OK)

    def export_identity_context(self) -> str:
        g = self._graphs[GraphScope.IDENTITY]
        lines = [f"{n}: {d}" for n, d in g.nodes(data=True)]
        return "\n".join(lines)

    async def update_identity_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        from datetime import datetime, timezone
        # Validate update data structure
        if not self._validate_identity_update(update_data):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Invalid identity update format"
            )
        # Check for required WA authorization
        if not update_data.get("wa_authorized"):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Identity updates require WA authorization"
            )
        # Process updates
        identity_graph = self._graphs[GraphScope.IDENTITY]
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                if identity_graph.has_node(node_id):
                    identity_graph.remove_node(node_id)
            else:
                # Update or create
                attrs = node_update.get("attributes", {})
                attrs["updated_by"] = update_data.get("wa_user_id", "unknown")
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                identity_graph.add_node(node_id, **attrs)
        # Update edges
        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            if edge_update.get("action") == "delete":
                if identity_graph.has_edge(source, target):
                    identity_graph.remove_edge(source, target)
            else:
                attrs = edge_update.get("attributes", {})
                identity_graph.add_edge(source, target, **attrs)
        await asyncio.to_thread(self._persist)
        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    async def update_environment_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update environment graph based on WA feedback."""
        from datetime import datetime, timezone
        # Example: No WA required, but could add more validation as needed
        environment_graph = self._graphs[GraphScope.ENVIRONMENT]
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                if environment_graph.has_node(node_id):
                    environment_graph.remove_node(node_id)
            else:
                attrs = node_update.get("attributes", {})
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                environment_graph.add_node(node_id, **attrs)
        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            if edge_update.get("action") == "delete":
                if environment_graph.has_edge(source, target):
                    environment_graph.remove_edge(source, target)
            else:
                attrs = edge_update.get("attributes", {})
                environment_graph.add_edge(source, target, **attrs)
        await asyncio.to_thread(self._persist)
        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    def _validate_identity_update(self, update_data: Dict[str, Any]) -> bool:
        """Validate identity update structure."""
        required_fields = ["wa_user_id", "wa_authorized", "update_timestamp"]
        if not all(field in update_data for field in required_fields):
            return False
        for node in update_data.get("nodes", []):
            if "id" not in node or "type" not in node:
                return False
            if node["type"] != NodeType.CONCEPT:
                return False
        return True

    def get_recent_completed_tasks(self, limit: int = 10):
        """Delegate to persistence layer for recent completed tasks."""
        from ciris_engine.persistence.tasks import get_recent_completed_tasks
        return get_recent_completed_tasks(limit)

    def get_top_tasks(self, limit: int = 10):
        """Delegate to persistence layer for top tasks."""
        from ciris_engine.persistence.tasks import get_top_tasks
        return get_top_tasks(limit)

    def count_tasks(self, status: Optional[TaskStatus] = None) -> int:
        """Delegate to persistence layer for task count, optionally filtered by status."""
        from ciris_engine.persistence.tasks import count_tasks
        return count_tasks(status=status)

    def count_thoughts(self) -> int:
        """Delegate to persistence layer for count of active or pending thoughts only."""
        from ciris_engine.persistence.thoughts import count_thoughts
        return count_thoughts()
