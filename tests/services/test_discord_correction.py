import os
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from ciris_engine.services.discord_deferral_sink import DiscordDeferralSink
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.core import persistence

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
