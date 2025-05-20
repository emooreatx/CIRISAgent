import pytest
from pathlib import Path
from unittest.mock import AsyncMock
import pickle
import networkx as nx

from ciris_engine.services.discord_graph_memory import (
    DiscordGraphMemory,
    MemoryOpStatus,
)
from ciris_engine.services.discord_observer import DiscordObserver
from ciris_engine.services.discord_event_queue import DiscordEventQueue
from ciris_engine.runtime.base_runtime import IncomingMessage


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
async def test_memorize_channel_write(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    result = await service.memorize("alice", "general", {"kind": "nice"})
    assert result.status == MemoryOpStatus.SAVED
    data = await service.remember("alice")
    assert data["kind"] == "nice"
    assert "alice" in service.graph


@pytest.mark.asyncio
async def test_user_memorize_no_channel(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    result = await service.memorize("bob", None, {"score": 1})
    assert result.status == MemoryOpStatus.SAVED
    data = await service.remember("bob")
    assert data["score"] == 1


@pytest.mark.asyncio
async def test_observe_does_not_modify_graph(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    dispatch_mock = AsyncMock()
    q = DiscordEventQueue()
    observer = DiscordObserver(dispatch_mock, message_queue=q, monitored_channel_id="general")
    msg = IncomingMessage(message_id="1", author_id="1", author_name="bob", content="hi", channel_id="general")
    await observer.handle_incoming_message(msg)

    dispatch_mock.assert_awaited_once()
    assert len(service.graph.nodes) == 0


@pytest.mark.asyncio
async def test_observe_queries_graph(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    remember_mock = AsyncMock()
    service.remember = remember_mock

    q = DiscordEventQueue()
    observer = DiscordObserver(
        lambda payload: service.remember(payload["context"]["author_name"]),
        message_queue=q,
        monitored_channel_id="general"
    )
    msg = IncomingMessage(message_id="2", author_id="2", author_name="carol", content="hello", channel_id="general")
    await observer.handle_incoming_message(msg)

    remember_mock.assert_awaited_once_with("carol")


@pytest.mark.asyncio
async def test_graph_persistence_roundtrip(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    result = await service.memorize("dave", "general", {"level": 5})
    assert result.status == MemoryOpStatus.SAVED
    await service.stop()

    new_service = DiscordGraphMemory(str(storage))
    await new_service.start()
    data = await new_service.remember("dave")
    assert data["level"] == 5
