import logging
import asyncio
import pickle
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

import networkx as nx

from .base import Service

logger = logging.getLogger(__name__)


class MemoryOpStatus(str, Enum):
    SAVED = "saved"
    DEFERRED = "deferred"
    FAILED = "failed"


class MemoryOpResult(BaseModel):
    status: MemoryOpStatus
    reason: Optional[str] = None
    deferral_package: Optional[Dict[str, Any]] = None


class DiscordGraphMemory(Service):
    """Persist user metadata in a lightweight NetworkX graph for Discord."""

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.storage_path = Path(storage_path or "memory_graph.pkl")
        if self.storage_path.exists():
            try:
                with self.storage_path.open("rb") as f:
                    self.graph = pickle.load(f)
                logger.info("Loaded memory graph from %s", self.storage_path)
            except Exception as exc:
                logger.warning("Failed to load memory graph in __init__: %s", exc)
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()

    def _persist(self):
        try:
            with self.storage_path.open("wb") as f:
                pickle.dump(self.graph, f)
        except Exception as exc:
            logger.warning("Failed to persist memory graph: %s", exc)

    async def start(self):
        await super().start()
        if self.storage_path.exists():
            try:
                with self.storage_path.open("rb") as f:
                    self.graph = pickle.load(f)
                logger.info("Loaded memory graph from %s", self.storage_path)
            except Exception as exc:
                logger.warning("Failed to load memory graph: %s", exc)
                self.graph = nx.DiGraph()
        else:
            self.graph = nx.DiGraph()
            logger.info("Initialized new memory graph")

    async def stop(self):
        self._persist()
        logger.info("Persisted memory graph to %s", self.storage_path)
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

        node_data = self.graph.nodes.get(user_nick, {})
        if channel:
            channels = set(node_data.get("channels", []))
            channels.add(channel)
            node_data["channels"] = list(channels)
            if channel_metadata:
                chan_meta = node_data.get("channel_metadata", {})
                chan_meta[channel] = channel_metadata
                node_data["channel_metadata"] = chan_meta
        
        node_data.update(metadata)
        self.graph.add_node(user_nick, **node_data)
        await asyncio.to_thread(self._persist)
        return MemoryOpResult(status=MemoryOpStatus.SAVED)

    async def remember(self, user_nick: str) -> Dict[str, Any]:
        if self.graph.has_node(user_nick):
            return dict(self.graph.nodes[user_nick])
        return {}

    async def forget(self, user_nick: str):
        if self.graph.has_node(user_nick):
            self.graph.remove_node(user_nick)
            await asyncio.to_thread(self._persist)
