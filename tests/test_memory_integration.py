import asyncio
import pytest
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

@pytest.mark.asyncio
async def test_memory_operations():
    memory = CIRISLocalGraph(":memory:")
    await memory.start()
    
    # Test memorize
    node = GraphNode(
        id="test_key",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={"value": "test_data"}
    )
    result = await memory.memorize(node)
    assert result.status.value == "ok"
    
    # Test remember
    result = await memory.remember("test_key", GraphScope.LOCAL)
    assert result.status.value == "ok"
    assert result.data["value"] == "test_data"
    
    # Test forget
    result = await memory.forget("test_key", GraphScope.LOCAL)
    assert result.status.value == "ok"
    
    await memory.stop()
