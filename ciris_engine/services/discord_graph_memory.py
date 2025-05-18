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
        self.approved_channels: set[str] = set()
        self._pending: Dict[str, list[tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]]] = {}
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
    ) -> bool:
        """Add or update a user's metadata. Returns True if finalized."""
        if not user_nick:
            logger.warning("Memorize called without a user nickname; skipping")
            return False

        if channel:
            if channel not in self.approved_channels:
                self._pending.setdefault(channel, []).append((user_nick, metadata, channel_metadata))
                logger.info("DEFER triggered for channel %s", channel)
                return False

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
        return True

    async def approve_channel(self, channel: str):
        self.approved_channels.add(channel)
        queued = self._pending.pop(channel, [])
        for user_nick, metadata, chan_meta in queued:
            await self.memorize(user_nick, channel, metadata, chan_meta)

    async def remember(self, user_nick: str) -> Dict[str, Any]:
        if self.graph.has_node(user_nick):
            return dict(self.graph.nodes[user_nick])
        return {}

    async def forget(self, user_nick: str):
        if self.graph.has_node(user_nick):
            self.graph.remove_node(user_nick)
            await asyncio.to_thread(self._persist)
