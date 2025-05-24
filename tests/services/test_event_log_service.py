import asyncio
from pathlib import Path

import pytest

from ciris_engine.services.event_log_service import EventLogService


@pytest.mark.asyncio
async def test_event_logging_and_rotation(tmp_path: Path):
    log_file = tmp_path / "events.jsonl"
    service = EventLogService(log_path=str(log_file), max_bytes=50, backups=1)
    await service.start()

    await service.log_event({"event": 1})
    await service.log_event({"event": 2})
    assert log_file.exists()
    lines_before = log_file.read_text().splitlines()
    assert len(lines_before) == 2

    # Force log to exceed max_bytes
    await service.log_event({"event": "x" * 60})
    await service.rotate()

    rotated = log_file.with_name("events.1.jsonl")
    assert rotated.exists()
    await service.stop()
