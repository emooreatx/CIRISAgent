import asyncio
import pytest
from unittest.mock import AsyncMock

from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider, GraphQLClient
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.core.graph_schemas import GraphNode, GraphScope, NodeType

class DummyTask:
    def __init__(self, author):
        self.context = {"author_name": author}

class DummyThought:
    def __init__(self, history=None):
        self.processing_context = {"history": history or []}

def _mk_client(response):
    client = GraphQLClient()
    client.query = AsyncMock(return_value=response)
    return client

@pytest.mark.asyncio
async def test_fallback_to_memory(tmp_path):
    mem = CIRISLocalGraph(str(tmp_path / "graph.pkl"))
    await mem.start()
    node = GraphNode(id="alice", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"nick": "AliceNick", "channel": "general"})
    await mem.memorize(node)

    client = _mk_client({})
    provider = GraphQLContextProvider(graphql_client=client, memory_service=mem)
    result = await provider.enrich_context(DummyTask("alice"), DummyThought())

    assert "user_profiles" in result
    assert result["user_profiles"]["alice"]["nick"] == "AliceNick"
    client.query.assert_not_called()

@pytest.mark.asyncio
async def test_partial_fallback(tmp_path):
    mem = CIRISLocalGraph(str(tmp_path / "graph.pkl"))
    await mem.start()
    node_bob = GraphNode(id="bob", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"nick": "Bobby", "channel": "random"})
    await mem.memorize(node_bob)

    graphql_response = {"users": [{"name": "alice", "nick": "Alice", "channel": "general"}]}
    client = _mk_client(graphql_response)
    history = [{"author_name": "bob"}]
    provider = GraphQLContextProvider(graphql_client=client, memory_service=mem, enable_remote_graphql=True)
    result = await provider.enrich_context(DummyTask("alice"), DummyThought(history))

    assert result["user_profiles"]["alice"]["nick"] == "Alice"
    assert result["user_profiles"]["bob"]["nick"] == "Bobby"
    client.query.assert_called_once()
