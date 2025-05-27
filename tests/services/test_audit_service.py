import json
import asyncio
from pathlib import Path

import pytest

from ciris_engine.services.audit_service import AuditService
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

@pytest.mark.asyncio
async def test_log_action_writes_line(tmp_path):
    log_file = tmp_path / "audit.jsonl"
    service = AuditService(log_path=str(log_file))
    context = {
        "originator_id": "agent:test",
        "target_id": "task:1",
        "event_summary": "test",
        "event_payload": {"k": "v"},
    }

    await service.log_action(HandlerActionType.SPEAK, context)

    data = log_file.read_text().strip().splitlines()
    assert len(data) == 1
    entry = json.loads(data[0])
    assert entry["event_type"] == "SPEAK"
    assert entry["originator_id"] == "agent:test"
    assert entry["target_id"] == "task:1"
