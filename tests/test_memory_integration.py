import asyncio
import pytest
import tempfile
import os
from ciris_engine.services.memory_service import LocalGraphMemoryService
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.memory_schemas_v1 import MemoryQuery

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
        recall_query = MemoryQuery(
            node_id="test_key",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )
        results = await memory.recall(recall_query)
        assert len(results) == 1
        assert results[0].id == "test_key"
        assert results[0].attributes["value"] == "test_data"
        
        # Test forget - forget takes a GraphNode
        forget_node = GraphNode(id="test_key", type=NodeType.CONCEPT, scope=GraphScope.LOCAL)
        result = await memory.forget(forget_node)
        assert result.status.value == "ok"
        
        await memory.stop()
    finally:
        # Clean up the temporary file
        if os.path.exists(db_path):
            os.unlink(db_path)
