import asyncio
import pytest
import tempfile
from pathlib import Path
from ciris_engine.secrets.store import SecretsStore
from ciris_engine.schemas.secrets_schemas_v1 import DetectedSecret
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel

@pytest.fixture
def temp_store():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "store.db"
        store = SecretsStore(str(db_path))
        yield store

@pytest.mark.asyncio
async def test_access_logs_and_reencrypt(temp_store):
    secret = DetectedSecret(
        secret_uuid="uuid-log",
        original_value="secretval123",
        replacement_text="{SECRET:uuid-log:log}",
        pattern_name="api_keys",
        description="desc",
        sensitivity=SensitivityLevel.HIGH,
        context_hint="ctx"
    )
    await temp_store.store_secret(secret)
    await temp_store.retrieve_secret("uuid-log")
    logs = await temp_store.get_access_logs("uuid-log")
    assert logs
    new_key = b"b" * 32
    assert await temp_store.reencrypt_all(new_key) is False

