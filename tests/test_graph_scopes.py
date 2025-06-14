import pytest
import tempfile
import os
from ciris_engine.services.memory_service import LocalGraphMemoryService


@pytest.mark.asyncio
async def test_identity_graph_updates():
    # Create a temporary database file (not :memory:) 
    # because :memory: creates separate databases per connection
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        db_path = tmp_file.name
    
    try:
        memory = LocalGraphMemoryService(db_path)
        await memory.start()
        
        # Test WA authorization required for identity
        update_data = {
            "wa_user_id": "test_wa",
            "wa_authorized": True,
            "update_timestamp": "2025-01-01T00:00:00Z",
            "nodes": [{
                "id": "test_concept",
                "type": "concept",
                "attributes": {"meaning": "test"}
            }]
        }
        
        result = await memory.update_identity_graph(update_data)
        assert result.status.value == "ok"
        await memory.stop()
    finally:
        # Clean up the temporary file
        if os.path.exists(db_path):
            os.unlink(db_path)
