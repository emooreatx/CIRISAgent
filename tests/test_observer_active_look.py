import os
import pytest
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from ciris_engine.schemas.action_params_v1 import ObserveParams, SpeakParams
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine import persistence

# The actual observer handler is defined inside run_discord_teacher.main.
# For unit testing we replicate the essential logic here.
async def observer_handler(runtime_ref, result, ctx):
    if not isinstance(result.action_parameters, ObserveParams):
        return
    if not result.action_parameters.perform_active_look:
        return

    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not channel_id:
        return

    try:
        channel = runtime_ref.io_adapter.client.get_channel(int(channel_id))
        msgs = []
        async for m in channel.history(limit=10):
            msgs.append(m)
    except Exception:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    new_th = Thought(
        thought_id="new", source_task_id=ctx.get("source_task_id"), thought_type="active_observation_result",
        status=ThoughtStatus.PENDING, created_at=now_iso, updated_at=now_iso, round_created=ctx.get("current_round_number",0),
        content=f"Active look observation from channel {channel_id}: Found {len(msgs)} messages.")
    persistence.add_thought(new_th)

class FakeMessage:
    def __init__(self, msg_id, content):
        self.id = msg_id
        self.content = content
        self.author = SimpleNamespace(id=1, name="tester")
        self.created_at = datetime.now(timezone.utc)

class FakeChannel:
    def __init__(self, messages):
        self._messages = messages
    def history(self, limit=10):
        async def gen():
            for m in self._messages[:limit]:
                yield m
        return gen()

class FakeClient:
    def __init__(self, channel):
        self._channel = channel
    def get_channel(self, cid):
        return self._channel

class FakeRuntime:
    def __init__(self, client):
        self.io_adapter = SimpleNamespace(client=client)

@pytest.mark.asyncio
async def test_observer_handler_active_look_creates_thought(monkeypatch):
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    msgs = [FakeMessage(1, "hi"), FakeMessage(2, "there")]
    channel = FakeChannel(msgs)
    runtime = FakeRuntime(FakeClient(channel))

    added = []
    monkeypatch.setattr(persistence, "add_thought", lambda t: added.append(t))
    monkeypatch.setattr(persistence, "update_thought_status", lambda *a, **k: None)

    params = ObserveParams(sources=["discord"], perform_active_look=True)
    result = ActionSelectionResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.OBSERVE,
        action_parameters=params,
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    ctx = {"thought_id": "th0", "source_task_id": "task1", "current_round_number": 0, "priority": 1}

    await observer_handler(runtime, result, ctx)
    assert len(added) == 1
    new_th = added[0]
    assert new_th.thought_type == "active_observation_result"
    assert new_th.source_task_id == "task1"

@pytest.mark.asyncio
async def test_active_look_pipeline(monkeypatch):
    monkeypatch.setenv("DISCORD_CHANNEL_ID", "1")
    msgs = [FakeMessage(1, "hi")]
    channel = FakeChannel(msgs)
    runtime = FakeRuntime(FakeClient(channel))

    added = []
    monkeypatch.setattr(persistence, "add_thought", lambda t: added.append(t))
    monkeypatch.setattr(persistence, "update_thought_status", lambda *a, **k: None)

    obs_params = ObserveParams(sources=["discord"], perform_active_look=True)
    obs_result = ActionSelectionResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.OBSERVE,
        action_parameters=obs_params,
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    ctx = {"thought_id": "th0", "source_task_id": "task1", "current_round_number": 0, "priority": 1}
    await observer_handler(runtime, obs_result, ctx)
    assert added
    active_th = added[0]

    speak_params = SpeakParams(content="done")
    speak_result = ActionSelectionResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=speak_params,
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )

    sink = SimpleNamespace(send_message=AsyncMock())
    handler = SpeakHandler(ActionHandlerDependencies(action_sink=sink))
    monkeypatch.setattr(persistence, "add_thought", lambda th: None)
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: None)
    await handler.handle(speak_result, active_th, {"channel_id": "1"})
    sink.send_message.assert_awaited()
