import pytest
from pathlib import Path
from unittest.mock import AsyncMock
import pickle
import networkx as nx

from ciris_engine.services.discord_graph_memory import (
    DiscordGraphMemory,
    MemoryOpStatus,
)
from ciris_engine.core.graph_schemas import GraphNode, GraphScope, NodeType
from ciris_engine.services.discord_observer import DiscordObserver
from ciris_engine.services.discord_event_queue import DiscordEventQueue
from ciris_engine.runtime.base_runtime import IncomingMessage


@pytest.mark.asyncio
async def test_memory_graph_starts_empty(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    result = await service.remember("alice", GraphScope.LOCAL)
    assert result.data is None


@pytest.mark.asyncio
async def test_memory_graph_loads_existing(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    g = nx.DiGraph()
    g.add_node("alice", kind="nice")
    data = {GraphScope.LOCAL.value: g}
    with storage.open("wb") as f:
        pickle.dump(data, f)

    service = DiscordGraphMemory(str(storage))
    result = await service.remember("alice", GraphScope.LOCAL)
    assert result.data["kind"] == "nice"


@pytest.mark.asyncio
async def test_memorize_channel_write(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    node = GraphNode(id="alice", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"kind": "nice"})
    result = await service.memorize(node)
    assert result.status == MemoryOpStatus.OK
    data = await service.remember("alice", GraphScope.LOCAL)
    assert data.data["kind"] == "nice"


@pytest.mark.asyncio
async def test_user_memorize_no_channel(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()
    node = GraphNode(id="bob", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"score": 1})
    result = await service.memorize(node)
    assert result.status == MemoryOpStatus.OK
    data = await service.remember("bob", GraphScope.LOCAL)
    assert data.data["score"] == 1


@pytest.mark.asyncio
async def test_observe_does_not_modify_graph(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    dispatch_mock = AsyncMock()
    q = DiscordEventQueue()
    observer = DiscordObserver(dispatch_mock, message_queue=q, monitored_channel_id="general")
    msg = IncomingMessage(message_id="1", author_id="1", author_name="bob", content="hi", channel_id="general", reference_message_id=None)
    await observer.handle_incoming_message(msg)

    dispatch_mock.assert_awaited_once()
    assert service.graph.number_of_nodes() == 0


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
    msg = IncomingMessage(message_id="2", author_id="2", author_name="carol", content="hello", channel_id="general", reference_message_id=None)
    await observer.handle_incoming_message(msg)

    remember_mock.assert_awaited_once_with("carol")


@pytest.mark.asyncio
async def test_graph_persistence_roundtrip(tmp_path: Path):
    storage = tmp_path / "graph.pkl"
    service = DiscordGraphMemory(str(storage))
    await service.start()

    node = GraphNode(id="dave", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"level": 5})
    result = await service.memorize(node)
    assert result.status == MemoryOpStatus.OK
    await service.stop()

    new_service = DiscordGraphMemory(str(storage))
    await new_service.start()
    data = await new_service.remember("dave", GraphScope.LOCAL)
    assert data.data["level"] == 5


@pytest.mark.asyncio
async def test_memorize_and_remember_multiple_key_values(tmp_path: Path):
    """
    Tests that multiple key-value pairs memorized for a user can be
    retrieved correctly.
    """
    storage_path = tmp_path / "test_multi_key_graph.pkl"
    service = DiscordGraphMemory(str(storage_path))
    await service.start()

    user_nick = "test_user_multi"
    user_data_to_memorize = {
        "real_name": "Testy McTestface",
        "favorite_color": "chartreuse",
        "score": 12345,
        "is_active": True,
        "preferences": {"notifications": "on", "theme": "dark"},
        "tags": ["vip", "beta_tester"]
    }

    # Memorize the data for the user (no specific channel, so it's user-level)
    node = GraphNode(id=user_nick, type=NodeType.USER, scope=GraphScope.LOCAL, attrs=user_data_to_memorize)
    memorize_result = await service.memorize(node)
    assert memorize_result.status == MemoryOpStatus.OK
    assert user_nick in service.graph
    # The user_data_to_memorize items are stored as direct attributes on the node,
    # not under a single 'data' key when channel is None.
    # The check below using service.remember() will validate the content.

    # Remember the user's data
    retrieved = await service.remember(user_nick, GraphScope.LOCAL)
    retrieved_data = retrieved.data
    assert retrieved_data is not None, "Retrieved data should not be None"
    
    # Assert that all original key-value pairs are present in the retrieved data
    for key, expected_value in user_data_to_memorize.items():
        assert key in retrieved_data, f"Key '{key}' should be in retrieved data"
        assert retrieved_data[key] == expected_value, \
            f"Value for key '{key}' should be '{expected_value}', but got '{retrieved_data[key]}'"
    
    # Ensure no extra keys were added (optional, but good for this test)
    assert len(retrieved_data.keys()) == len(user_data_to_memorize.keys()), \
        "Retrieved data should have the same number of keys as memorized data"

    await service.stop()
