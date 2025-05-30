import pytest
import asyncio
from ciris_engine.adapters import EventLogService

@pytest.mark.asyncio
async def test_log_event_and_rotate(tmp_path):
    log_path = tmp_path / "events.jsonl"
    service = EventLogService(log_path=str(log_path), max_bytes=100, backups=2)
    await service.start()
    await service.log_event({"foo": "bar"})
    await service.rotate()
    assert log_path.exists()
    await service.stop()
