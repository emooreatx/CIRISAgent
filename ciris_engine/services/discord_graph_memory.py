import logging
import asyncio
import pickle
from pathlib import Path
from typing import Dict, Any, Optional

import networkx as nx

from .base import Service

logger = logging.getLogger(__name__)


class DiscordGraphMemory(Service):
    """Persist user metadata in a lightweight NetworkX graph for Discord."""

    def __init__(self, storage_path: Optional[str] = None):
        super().__init__()
        self.storage_path = Path(storage_path or "memory_graph.pkl")
        self.graph: nx.DiGraph = nx.DiGraph()

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

    async def memorize(self, user_nick: str, channel: str, metadata: Dict[str, Any]):
        """Add or update a user's metadata in the graph."""
        node_data = self.graph.nodes.get(user_nick, {})
        channels = set(node_data.get("channels", []))
        channels.add(channel)
        node_data.update(metadata)
        node_data["channels"] = list(channels)
        self.graph.add_node(user_nick, **node_data)
        await asyncio.to_thread(self._persist)

    async def remember(self, user_nick: str) -> Dict[str, Any]:
        if self.graph.has_node(user_nick):
            return dict(self.graph.nodes[user_nick])
        return {}

    async def forget(self, user_nick: str):
        if self.graph.has_node(user_nick):
            self.graph.remove_node(user_nick)
            await asyncio.to_thread(self._persist)
