import logging
import asyncio
import pickle
from pathlib import Path
from typing import Dict, Any, Optional

import networkx as nx

from pydantic import BaseModel
from ..core.graph_schemas import GraphNode, GraphEdge, GraphScope, GraphUpdateEvent, NodeType
from ..core.foundational_schemas import CaseInsensitiveEnum, CIRISAgentUAL
from .utils import sanitize_dict
from ..services.base import Service

logger = logging.getLogger(__name__)

class MemoryOpStatus(CaseInsensitiveEnum):
    SAVED = "saved"
    DEFERRED = "deferred"
    FAILED = "failed"

class MemoryOpResult(BaseModel):
    status: MemoryOpStatus
    data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None

class CIRISLocalGraph(Service):
    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.storage_path = Path(storage_path or "memory_graph.pkl")
        self._graphs = {
            GraphScope.LOCAL: nx.DiGraph(),
            GraphScope.IDENTITY: nx.DiGraph(),
            GraphScope.ENVIRONMENT: nx.DiGraph(),
        }
        if self.storage_path.exists():
            self._load()

    @property
    def graph(self):
        return self._graphs[GraphScope.LOCAL]

    def _load(self):
        try:
            with self.storage_path.open("rb") as f:
                data = pickle.load(f)
            for scope in GraphScope:
                g = data.get(scope.value)
                if isinstance(g, nx.DiGraph):
                    self._graphs[scope] = g
                else:
                    self._graphs[scope] = nx.DiGraph()
                    logger.warning("Init empty graph for scope %s", scope.value)
        except Exception as exc:
            logger.warning("Failed to load memory graphs: %s", exc)

    def _persist(self):
        try:
            to_dump = {scope.value: g for scope, g in self._graphs.items()}
            with self.storage_path.open("wb") as f:
                pickle.dump(to_dump, f)
        except Exception as exc:
            logger.error("Failed to persist memory graphs: %s", exc)

    async def start(self):
        await super().start()
        if self.storage_path.exists():
            self._load()

    async def stop(self):
        await asyncio.to_thread(self._persist)
        await super().stop()

    # Compatibility layer with previous DiscordGraphMemory API
    async def memorize(
        self,
        user_nick: str,
        channel: Optional[str],
        metadata: Dict[str, Any],
        channel_metadata: Optional[Dict[str, Any]] = None,
        *,
        is_correction: bool = False,
    ) -> MemoryOpResult:
        node = GraphNode(
            id=user_nick,
            type=NodeType.USER,
            scope=GraphScope.LOCAL,
            attrs={**metadata, "channel": channel} if channel else metadata,
        )
        event = GraphUpdateEvent(node=node, actor="local")
        return await self.apply_update(event)

    async def remember(self, user_nick: str) -> Dict[str, Any]:
        data = await self.remember_node(user_nick, GraphScope.LOCAL)
        return data or {}

    async def forget(self, user_nick: str):
        await self.forget_node(user_nick, GraphScope.LOCAL)

    async def apply_update(self, event: GraphUpdateEvent) -> MemoryOpResult:
        scope = event.node.scope if event.node else event.edge.scope  # type: ignore
        g = self._graphs.get(scope)
        if event.node:
            g.add_node(event.node.id, **sanitize_dict(event.node.attrs))
            await asyncio.to_thread(self._persist)
            return MemoryOpResult(status=MemoryOpStatus.SAVED)
        if event.edge:
            g.add_edge(event.edge.source, event.edge.target, label=event.edge.label.value)
            await asyncio.to_thread(self._persist)
            return MemoryOpResult(status=MemoryOpStatus.SAVED)
        return MemoryOpResult(status=MemoryOpStatus.FAILED, reason="empty event")

    async def remember_node(self, node_id: str, scope: GraphScope = GraphScope.LOCAL) -> Optional[Dict[str, Any]]:
        g = self._graphs.get(scope)
        if g and node_id in g:
            return dict(g.nodes[node_id])
        return None

    async def forget_node(self, node_id: str, scope: GraphScope = GraphScope.LOCAL) -> MemoryOpResult:
        g = self._graphs.get(scope)
        if g and node_id in g:
            g.remove_node(node_id)
            await asyncio.to_thread(self._persist)
            return MemoryOpResult(status=MemoryOpStatus.SAVED)
        return MemoryOpResult(status=MemoryOpStatus.FAILED, reason="not found")
