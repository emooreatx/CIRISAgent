import pytest
import tempfile
import os
from ciris_engine.logic.services.memory_service import LocalGraphMemoryService


@pytest.mark.asyncio
@pytest.mark.skip(reason="update_identity_graph method not implemented in current architecture")
async def test_identity_graph_updates():
    # Create a temporary database file (not :memory:)
    # because :memory: creates separate databases per connection
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        db_path = tmp_file.name

    try:
        memory = LocalGraphMemoryService(db_path)
        await memory.start()

        # Test WA authorization required for identity
        from ciris_engine.schemas.runtime.memory import IdentityUpdateRequest
        update_data = IdentityUpdateRequest(
            source="wa",
            node_id="test_concept",
            updates={"meaning": "test", "wa_authorized": "true"},
            reason="Test WA authorized update"
        )

        result = await memory.update_identity_graph(update_data)
        assert result.status.value == "ok"
        await memory.stop()
    finally:
        # Clean up the temporary file
        if os.path.exists(db_path):
            os.unlink(db_path)
