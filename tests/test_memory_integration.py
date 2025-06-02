import asyncio
import pytest
import tempfile
import os
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

@pytest.mark.asyncio
async def test_memory_operations():
    # Create a temporary database file (not :memory:) 
    # because :memory: creates separate databases per connection
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        memory = LocalGraphMemoryService(db_path)
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
        
        # Test recall
        recall_node = GraphNode(id="test_key", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
        result = await memory.recall(recall_node)
        assert result.status.value == "ok"
        assert result.data["value"] == "test_data"
        
        # Test forget
        result = await memory.forget(recall_node)
        assert result.status.value == "ok"
        
        await memory.stop()
    finally:
        # Clean up the temporary file
        if os.path.exists(db_path):
            os.unlink(db_path)
