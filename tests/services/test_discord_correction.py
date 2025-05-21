import os
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from ciris_engine.services.discord_deferral_sink import DiscordDeferralSink
from ciris_engine.core.agent_core_schemas import Task, Thought
from ciris_engine.core.foundational_schemas import IncomingMessage
from pathlib import Path
from ciris_engine.core import persistence

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_service.db"

@pytest.fixture
def mock_db_path(monkeypatch, db_path: Path):
    monkeypatch.setattr(persistence, "get_sqlite_db_full_path", lambda: str(db_path))

@pytest.fixture
def initialized_db(mock_db_path):
    persistence.initialize_database()
    yield

@pytest.mark.asyncio
async def test_create_correction_thought(monkeypatch):
    adapter = SimpleNamespace(client=SimpleNamespace())
    service = DiscordDeferralSink(adapter, "1")

    added = {}
    monkeypatch.setattr(persistence, "add_thought", lambda t: added.update({"thought": t}))
    monkeypatch.setattr(persistence, "get_task_by_id", lambda tid: Task(task_id=tid, description="d", created_at="", updated_at=""))

    msg = SimpleNamespace(
        author=SimpleNamespace(id=2, name="wa"),
        id=3,
        content="fix",
        created_at=datetime.now(timezone.utc),
    )

    service._create_correction_thought("task1", "th0", msg, None)
    assert added["thought"].source_task_id == "task1"
    assert added["thought"].related_thought_id == "th0"

@pytest.mark.asyncio
async def test_correction_fallback_to_stored_package(initialized_db, monkeypatch):
    adapter = SimpleNamespace(client=SimpleNamespace())
    service = DiscordDeferralSink(adapter, "1")

    # persist mapping with package
    pkg = {"foo": "bar"}
    now = datetime.now(timezone.utc).isoformat()
    persistence.add_task(Task(task_id="t", description="d", created_at=now, updated_at=now))
    persistence.add_thought(
        Thought(
            thought_id="th",
            source_task_id="t",
            thought_type="t",
            content="c",
            created_at=now,
            updated_at=now,
            round_created=0,
        )
    )
    persistence.save_deferral_report_mapping("99", "t", "th", pkg)

    captured = {}
    def fake_create(task_id, thought_id, msg, package):
        captured["package"] = package
    monkeypatch.setattr(service, "_create_correction_thought", fake_create)

    msg = IncomingMessage(
        message_id="m", author_id="2", author_name="wa", content="c", channel_id="1", reference_message_id="99"
    )
    raw = SimpleNamespace(reference=SimpleNamespace(message_id="99", resolved=SimpleNamespace(content="no json")), author=SimpleNamespace(id=2, name="wa"), id=5, content="c", created_at=datetime.now(timezone.utc))

    handled = await service.process_possible_correction(msg, raw)
    assert handled
    assert captured["package"] == pkg
