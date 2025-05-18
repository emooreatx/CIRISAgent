import pytest
from pathlib import Path
from unittest.mock import AsyncMock

from ciris_engine.services.discord_graph_memory import DiscordGraphMemory
from ciris_engine.services.discord_observer import DiscordObserver


@pytest.mark.asyncio
async def test_memory_graph_starts_empty(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    assert len(service.graph.nodes) == 0


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
