from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ciris_engine.services.cirisnode_client import CIRISNodeClient
from ciris_engine.services.audit_service import AuditService
from ciris_engine.core.audit_schemas import AuditLogEntry


@pytest.fixture
def mock_async_client(monkeypatch):
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"ok": True}
    mock_response.raise_for_status.return_value = None
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.put.return_value = mock_response
    monkeypatch.setattr(
        "ciris_engine.services.cirisnode_client.httpx.AsyncClient",
        MagicMock(return_value=mock_client),
    )
    return mock_client


@pytest.mark.asyncio
async def test_cirisnode_client_logs_he300(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.run_he300("m1", "a1")

    mock_async_client.post.assert_awaited_once_with(
        "/he300", json={"model_id": "m1", "agent_id": "a1"}
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_type == "cirisnode_test"
    assert entry.originator_id == "a1"


@pytest.mark.asyncio
async def test_cirisnode_client_logs_chaos(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.run_chaos_tests("agentX", ["s1", "s2"])

    mock_async_client.post.assert_awaited_once_with(
        "/chaos", json={"agent_id": "agentX", "scenarios": ["s1", "s2"]}
    )
    assert result == {"ok": True}

    lines = log_file.read_text().splitlines()
    entry = AuditLogEntry.model_validate_json(lines[0])
    assert entry.event_type == "cirisnode_test"
    assert entry.originator_id == "agentX"


@pytest.mark.asyncio
async def test_cirisnode_client_logs_simplebench(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.run_simplebench("m2", "agentY")

    mock_async_client.post.assert_awaited_once_with(
        "/simplebench", json={"model_id": "m2", "agent_id": "agentY"}
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_summary == "simplebench"


@pytest.mark.asyncio
async def test_cirisnode_client_logs_wa_service(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.run_wa_service("eval", {"agent_id": "wa1", "data": 1})

    mock_async_client.post.assert_awaited_once_with(
        "/wa/eval", json={"agent_id": "wa1", "data": 1}
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_summary == "wa"


@pytest.mark.asyncio
async def test_cirisnode_client_logs_event(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.log_event({"event_type": "test", "originator_id": "e1"})

    mock_async_client.post.assert_awaited_once_with(
        "/events", json={"event_type": "test", "originator_id": "e1"}
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_type == "cirisnode_event"


@pytest.mark.asyncio
async def test_fetch_benchmark_prompts(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.fetch_benchmark_prompts("demo", "m3", "agentZ")

    mock_async_client.get.assert_awaited_once_with(
        "/bench/demo/prompts", params={"model_id": "m3", "agent_id": "agentZ"}
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_summary == "demo_prompts"


@pytest.mark.asyncio
async def test_submit_benchmark_answers(tmp_path: Path, mock_async_client):
    log_file = tmp_path / "audit.jsonl"
    audit = AuditService(log_path=str(log_file))
    client = CIRISNodeClient(audit_service=audit, base_url="http://test")

    result = await client.submit_benchmark_answers(
        "demo", "m4", "agentW", [{"id": 1, "answer": "42"}]
    )

    mock_async_client.put.assert_awaited_once_with(
        "/bench/demo/answers",
        json={
            "model_id": "m4",
            "agent_id": "agentW",
            "answers": [{"id": 1, "answer": "42"}],
        },
    )
    assert result == {"ok": True}

    entry = AuditLogEntry.model_validate_json(log_file.read_text().splitlines()[0])
    assert entry.event_summary == "demo_answers"
