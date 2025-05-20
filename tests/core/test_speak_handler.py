import pytest
from ciris_engine.core.agent_core_schemas import Thought
from ciris_engine.core.action_handlers.speak_handler import handle_speak

class DummyDiscord:
    def __init__(self):
        self.sent = []
    async def send_message(self, target, content):
        self.sent.append((target, content))

@pytest.mark.asyncio
async def test_handle_speak():
    t = Thought(thought_id="t", source_task_id="task", created_at="", updated_at="", round_created=0, content="")
    svc = DummyDiscord()
    new_thought = await handle_speak(t, {"content": "hi", "target_channel": "c"}, svc)
    assert svc.sent == [("c", "hi")]
    assert new_thought.source_task_id == t.source_task_id
    assert new_thought.related_thought_id == t.thought_id
