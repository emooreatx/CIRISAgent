import pytest
from pathlib import Path
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph, MemoryOpStatus
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

@pytest.mark.asyncio
async def test_memory_action_roundtrip(tmp_path: Path):
    graph = CIRISLocalGraph(str(tmp_path / "g.pkl"))
    await graph.start()

    node = GraphNode(id="alice", type=NodeType.USER, scope=GraphScope.LOCAL, attrs={"age": 30})
    result = await graph.memorize(node)
    assert result.status == MemoryOpStatus.OK

    remember = await graph.remember("alice", GraphScope.LOCAL)
    assert remember.data["age"] == 30

    delete_res = await graph.forget("alice", GraphScope.LOCAL)
    assert delete_res.status == MemoryOpStatus.OK

    after = await graph.remember("alice", GraphScope.LOCAL)
    assert after.data is None
