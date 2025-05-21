import logging
import asyncio
import pickle
from ..core.foundational_schemas import CaseInsensitiveEnum
from ..core.graph_schemas import (
    GraphNode,
    GraphEdge,
    GraphScope,
    GraphUpdateEvent,
    NodeType,
)
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

import networkx as nx

from ..services.base import Service

logger = logging.getLogger(__name__)


def _sanitize_attrs(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Simple HTML sanitization using html.escape."""
    from html import escape

    clean = {}
    for k, v in attrs.items():
        if isinstance(v, str):
            clean[k] = escape(v)
        else:
            clean[k] = v
    return clean


class MemoryOpStatus(CaseInsensitiveEnum):
    SAVED = "saved"
    DEFERRED = "deferred"
    FAILED = "failed"


class MemoryOpResult(BaseModel):
    status: MemoryOpStatus
    reason: Optional[str] = None
    deferral_package: Optional[Dict[str, Any]] = None


class CIRISLocalGraph(Service):
    """Persist metadata in a lightweight NetworkX graph separated by scope."""

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.storage_path = Path(storage_path or "memory_graph.pkl")
        self._graphs = {
            GraphScope.LOCAL: nx.DiGraph(),
            GraphScope.IDENTITY: nx.DiGraph(),
            GraphScope.ENVIRONMENT: nx.DiGraph(),
        }
        if self.storage_path.exists():
            try:
                with self.storage_path.open("rb") as f:
                    data = pickle.load(f)
                for scope in self._graphs:
                    key = scope.value if isinstance(data, dict) else scope.value
                    g = data.get(key) if isinstance(data, dict) else None
                    if isinstance(g, nx.DiGraph):
                        self._graphs[scope] = g
                logger.info("Memory graphs loaded from %s", self.storage_path)
            except Exception as exc:
                logger.warning(
                    "Failed to load memory graph from %s (%s: %s)",
                    self.storage_path,
                    type(exc).__name__,
                    exc,
                )

    @property
    def graph(self) -> nx.DiGraph:
        """Backward-compatible access to the local graph."""
        return self._graphs[GraphScope.LOCAL]

    def _persist(self):
        try:
            with self.storage_path.open("wb") as f:
                pickle.dump(
                    {
                        GraphScope.LOCAL.value: self._graphs[GraphScope.LOCAL],
                        GraphScope.IDENTITY.value: self._graphs[GraphScope.IDENTITY],
                        GraphScope.ENVIRONMENT.value: self._graphs[GraphScope.ENVIRONMENT],
                    },
                    f,
                )
            logger.info(
                "Persisted memory graphs to %s",
                self.storage_path,
            )
        except Exception as exc:
            logger.warning("Failed to persist memory graph: %s", exc)

    async def start(self):
        await super().start()
        if self.storage_path.exists():
            try:
                with self.storage_path.open("rb") as f:
                    data = pickle.load(f)
                for scope in self._graphs:
                    g = None
                    if isinstance(data, dict):
                        g = data.get(scope.value)
                    if isinstance(g, nx.DiGraph):
                        self._graphs[scope] = g
                    else:
                        self._graphs[scope] = nx.DiGraph()
                logger.info("Loaded memory graphs from %s", self.storage_path)
            except Exception as exc:
                logger.warning("Failed to load memory graph: %s", exc)
                self._graphs = {s: nx.DiGraph() for s in GraphScope}
        else:
            self._graphs = {s: nx.DiGraph() for s in GraphScope}
            logger.info("Initialized new memory graphs")

    async def stop(self):
        self._persist()
        logger.info("Persisted memory graphs to %s", self.storage_path)
        await super().stop()

    async def memorize(
        self,
        user_nick: str,
        channel: Optional[str],
        metadata: Dict[str, Any],
        channel_metadata: Optional[Dict[str, Any]] = None,
        *,
        is_correction: bool = False,
    ) -> MemoryOpResult:
        """Add or update a user's metadata."""
        if not user_nick:
            logger.warning("Memorize called without a user nickname; skipping")
            return MemoryOpResult(status=MemoryOpStatus.FAILED, reason="missing user")

        graph = self._graphs[GraphScope.LOCAL]
        node_data = graph.nodes.get(user_nick, {})
        if channel:
            channels = set(node_data.get("channels", []))
            channels.add(channel)
            node_data["channels"] = list(channels)
            if channel_metadata:
                chan_meta = node_data.get("channel_metadata", {})
                chan_meta[channel] = channel_metadata
                node_data["channel_metadata"] = chan_meta

        node_data.update(_sanitize_attrs(metadata))
        node_data["type"] = NodeType.USER
        graph.add_node(user_nick, **node_data)
        try:
            await asyncio.to_thread(self._persist)
        except Exception as exc:
            logger.error("Async persist failed: %s", exc)
            return MemoryOpResult(status=MemoryOpStatus.FAILED, reason=str(exc))
        return MemoryOpResult(status=MemoryOpStatus.SAVED)

    async def remember(self, user_nick: str) -> Dict[str, Any]:
        graph = self._graphs[GraphScope.LOCAL]
        logger.info(f"Attempting to remember data for user_nick: {user_nick}")
        if graph.has_node(user_nick):
            user_data = dict(graph.nodes[user_nick])
            logger.info(f"Data found for user_nick: {user_nick}. Data: {user_data}")
            return user_data
        logger.info(f"No data found for user_nick: {user_nick}")
        return {}

    async def forget(self, user_nick: str):
        graph = self._graphs[GraphScope.LOCAL]
        if graph.has_node(user_nick):
            graph.remove_node(user_nick)
            await asyncio.to_thread(self._persist)

    async def apply_update(self, event: GraphUpdateEvent) -> MemoryOpStatus:
        scope = event.node.scope if event.node else event.edge.scope

        if scope == GraphScope.IDENTITY and event.actor != "wa":
            return MemoryOpStatus.DEFERRED
        if scope == GraphScope.ENVIRONMENT and event.actor != "external_sync" and event.actor != "wa":
            return MemoryOpStatus.FAILED

        graph = self._graphs[scope]
        if event.node:
            data = _sanitize_attrs(event.node.attrs)
            data["type"] = event.node.type
            graph.add_node(event.node.id, **data)
        if event.edge:
            edata = _sanitize_attrs(event.edge.attrs)
            graph.add_edge(event.edge.source, event.edge.target, label=event.edge.label, **edata)
        await asyncio.to_thread(self._persist)
        return MemoryOpStatus.SAVED

