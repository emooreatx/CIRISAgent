import pytest
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph

@pytest.mark.asyncio
async def test_identity_graph_updates():
    memory = CIRISLocalGraph(":memory:")
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
