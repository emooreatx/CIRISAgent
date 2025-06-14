import pytest
from ciris_engine.services.audit_service import AuditService
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
import asyncio

@pytest.mark.asyncio
async def test_log_action_and_flush(tmp_path):
    service = AuditService(log_path=tmp_path / "audit.jsonl", rotation_size_mb=1)
    await service.start()
    context = {"thought_id": "t1", "target_id": "u1", "agent_profile": "p", "round_number": 1, "task_id": "task1"}
    await service.log_action(HandlerActionType.SPEAK, context, outcome="ok")
    await service._flush_buffer()
    with open(tmp_path / "audit.jsonl") as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = AuditLogEntry.model_validate_json(lines[0])
    assert entry.event_type == HandlerActionType.SPEAK.value
    await service.stop()
