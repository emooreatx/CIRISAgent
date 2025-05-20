import os
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from ciris_engine.services.discord_service import DiscordService
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_core_schemas import Task
from ciris_engine.core import persistence

@pytest.mark.asyncio
async def test_create_correction_thought(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "x")
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")

    dispatcher = ActionDispatcher({})
    service = DiscordService(dispatcher)

    added = {}
    monkeypatch.setattr(persistence, "add_thought", lambda t: added.update({"thought": t}))
    monkeypatch.setattr(persistence, "get_task_by_id", lambda tid: Task(task_id=tid, description="d", created_at="", updated_at=""))

    msg = SimpleNamespace(
        author=SimpleNamespace(id=2, name="wa"),
        id=3,
        content="fix",
        created_at=datetime.now(timezone.utc),
    )

    new_th = service._create_correction_thought("task1", "th0", msg, None)
    assert added["thought"].source_task_id == "task1"
    assert added["thought"].related_thought_id == "th0"
    assert new_th == added["thought"]
