import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.schemas.service_actions_v1 import ObserveMessageAction
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

@pytest.mark.asyncio
async def test_process_observation_action_creates_entries(monkeypatch):
    runtime = CIRISRuntime(profile_name="default")
    dispatcher = MagicMock()
    dispatcher.dispatch = AsyncMock()
    runtime.agent_processor = MagicMock(action_dispatcher=dispatcher)

    added_tasks = []
    added_thoughts = []
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.persistence.add_task", lambda t: added_tasks.append(t))
    monkeypatch.setattr("ciris_engine.runtime.ciris_runtime.persistence.add_thought", lambda t: added_thoughts.append(t))

    msg = IncomingMessage(message_id="1", content="hello", author_id="u1", author_name="User", channel_id="c1")
    action = ObserveMessageAction(handler_name="ObserveHandler", metadata={}, message=msg)

    await runtime._process_observation_action(action)

    assert added_tasks, "task not added"
    assert added_thoughts, "thought not added"
    dispatcher.dispatch.assert_awaited()
