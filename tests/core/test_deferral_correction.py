from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from ciris_engine.services.discord_deferral_sink import DiscordDeferralSink
from ciris_engine.core.foundational_schemas import IncomingMessage
from ciris_engine.core.agent_core_schemas import Task, Thought
from ciris_engine.core import persistence


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "deferral_test.db"


@pytest.fixture
def mock_db_path(monkeypatch, db_path: Path):
    monkeypatch.setattr(persistence, "get_sqlite_db_full_path", lambda: str(db_path))


@pytest.fixture
def initialized_db(mock_db_path):
    persistence.initialize_database()
    yield


@pytest.mark.asyncio
async def test_stored_package_fallback(initialized_db, monkeypatch):
    adapter = SimpleNamespace(client=SimpleNamespace())
    sink = DiscordDeferralSink(adapter, "1")

    now = datetime.now(timezone.utc).isoformat()
    task = Task(task_id="t1", description="d", created_at=now, updated_at=now)
    thought = Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type="t",
        content="c",
        created_at=now,
        updated_at=now,
        round_created=0,
    )
    persistence.add_task(task)
    persistence.add_thought(thought)

    package = {"k": "v"}
    persistence.save_deferral_report_mapping("msg1", "t1", "th1", package)

    captured = {}

    def fake_create(task_id, corrected_th_id, msg, pkg):
        captured["pkg"] = pkg

    monkeypatch.setattr(sink, "_create_correction_thought", fake_create)

    raw = SimpleNamespace(
        reference=SimpleNamespace(message_id="msg1", resolved=SimpleNamespace(content="no json")),
        author=SimpleNamespace(id=2, name="wa"),
        id=3,
        content="fix",
        created_at=datetime.now(timezone.utc),
    )
    incoming = IncomingMessage(
        message_id="3", author_id="2", author_name="wa", content="fix", channel_id="1"
    )

    assert await sink.process_possible_correction(incoming, raw)
    assert captured.get("pkg") == package

