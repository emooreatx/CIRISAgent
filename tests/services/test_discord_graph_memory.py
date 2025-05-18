import pytest
from pathlib import Path
from unittest.mock import AsyncMock
import pickle
import networkx as nx

from ciris_engine.services.discord_graph_memory import DiscordGraphMemory
from ciris_engine.services.discord_observer import DiscordObserver


@pytest.mark.asyncio
async def test_memory_graph_starts_empty(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    assert len(service.graph.nodes) == 0


@pytest.mark.asyncio
async def test_memory_graph_loads_existing(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    g = nx.DiGraph()
    g.add_node("alice", kind="nice")
    with storage.open("wb") as f:
        pickle.dump(g, f)

    service = DiscordGraphMemory(str(storage))
    assert "alice" in service.graph


@pytest.mark.asyncio
async def test_memorize_creates_node(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    await service.memorize("alice", "general", {"kind": "nice"})
    data = await service.remember("alice")
    assert data["kind"] == "nice"
    assert "alice" in service.graph


@pytest.mark.asyncio
async def test_observe_does_not_modify_graph(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    dispatch_mock = AsyncMock()
    observer = DiscordObserver(dispatch_mock)
    await observer.handle_event("bob", "general")

    dispatch_mock.assert_awaited_once()
    assert len(service.graph.nodes) == 0


@pytest.mark.asyncio
async def test_observe_queries_graph(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    remember_mock = AsyncMock()
    service.remember = remember_mock

    observer = DiscordObserver(lambda payload: service.remember(payload["user_nick"]))
    await observer.handle_event("carol", "general")

    remember_mock.assert_awaited_once_with("carol")
