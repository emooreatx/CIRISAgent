import pytest
import tempfile
from pathlib import Path
from ciris_engine.secrets.service import SecretsService
from ciris_engine.schemas.config_schemas_v1 import SecretPattern
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel

@pytest.fixture
def temp_service():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "svc.db"
        service = SecretsService(db_path=str(db_path))
        yield service

@pytest.mark.asyncio
async def test_service_stats_and_auto_forget_controls(temp_service):
    await temp_service.process_incoming_text("api_key=sk_stats_1234567890123456")
    stats = await temp_service.get_service_stats()
    assert stats["filter_stats"]["total_patterns"] > 0
    assert stats["storage_stats"]["total_secrets"] >= 1
    temp_service.disable_auto_forget()
    assert not await temp_service.auto_forget_task_secrets()
    temp_service.enable_auto_forget()
    forgotten = await temp_service.auto_forget_task_secrets()
    assert len(forgotten) >= 1

