from __future__ import annotations
import logging
import pickle
from pathlib import Path
from typing import Dict, Optional, Any
import asyncio

import networkx as nx

from ..core.graph_schemas import (
    GraphScope,
    GraphNode,
    NodeType,
    GraphEdge,
    GraphUpdateEvent,
)
from ..core.foundational_schemas import CaseInsensitiveEnum
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
            attrs = metadata or {}
            node = GraphNode(id=str(user_nick), type=NodeType.USER, scope=scope, attrs=attrs)
        g = self._graphs[node.scope]
        g.add_node(node.id, **node.attrs)
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
