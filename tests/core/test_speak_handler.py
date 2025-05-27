import pytest
from ciris_engine.schemas.agent_core_schemas_v1 import (
    Thought,
    ActionSelectionPDMAResult,
    SpeakParams,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.action_handlers.speak_handler import SpeakHandler
from ciris_engine.exceptions import FollowUpCreationError
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine import persistence

class DummyDiscord:
    def __init__(self):
        self.sent = []
    async def send_message(self, target, content):
        self.sent.append((target, content))

@pytest.mark.asyncio
async def test_handle_speak(monkeypatch):
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    svc = DummyDiscord()
    deps = ActionHandlerDependencies(action_sink=svc)
    handler = SpeakHandler(deps)
    added = []
    monkeypatch.setattr(persistence, "add_thought", lambda th: added.append(th))
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: None)
    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi", target_channel="c"),
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )
    await handler.handle(result, t, {"channel_id": "c"})
    assert svc.sent == [("c", "hi")]
    assert added and added[0].related_thought_id == t.thought_id


@pytest.mark.asyncio
async def test_speak_follow_up_failure(monkeypatch):
    t = Thought(thought_id="t2", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    svc = DummyDiscord()
    deps = ActionHandlerDependencies(action_sink=svc)
    handler = SpeakHandler(deps)
    monkeypatch.setattr(persistence, "update_thought_status", lambda **k: None)

    def fail_add(_):
        raise Exception("boom")

    monkeypatch.setattr(persistence, "add_thought", fail_add)

    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi", target_channel="c"),
        action_selection_rationale="r",
        monitoring_for_selected_action="m",
    )

    with pytest.raises(FollowUpCreationError):
        await handler.handle(result, t, {"channel_id": "c"})
