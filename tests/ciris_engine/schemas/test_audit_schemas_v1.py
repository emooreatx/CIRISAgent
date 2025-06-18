from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry
from pydantic import ValidationError
import pytest

def test_audit_log_entry_minimal():
    entry = AuditLogEntry(
        event_id="e1",
        event_timestamp="2025-05-28T12:00:00Z",
        event_type="test",
        originator_id="agent1",
        event_summary="summary"
    )
    assert entry.event_id == "e1"
    assert entry.event_type == "test"
    assert entry.event_payload is None
    assert entry.round_number is None

def test_audit_log_entry_optional_fields():
    entry = AuditLogEntry(
        event_id="e2",
        event_timestamp="2025-05-28T12:00:00Z",
        event_type="test2",
        originator_id="agent2",
        event_summary="summary2",
        event_payload={"foo": "bar"},
        agent_template="template",
        round_number=2,
        thought_id="t1",
        task_id="task1"
    )
    assert entry.event_payload == {"foo": "bar"}
    assert entry.agent_template == "template"
    assert entry.round_number == 2
    assert entry.thought_id == "t1"
    assert entry.task_id == "task1"

def test_audit_log_entry_missing_required():
    with pytest.raises(ValidationError):
        AuditLogEntry(event_id="e3")
