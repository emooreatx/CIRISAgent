import asyncio
import pytest

from ciris_core import AgentState, Coordinator, Processor
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus


@pytest.mark.asyncio
async def test_set_state_creates_root_task():
    coord = Coordinator()
    proc = Processor(coord)
    proc.set_state(AgentState.WAKEUP)
    assert proc.current_state == AgentState.WAKEUP
    assert "wakeup" in proc.tasks
    root_task = proc.tasks["wakeup"]
    assert root_task.status == TaskStatus.ACTIVE


@pytest.mark.asyncio
async def test_process_round_completes_thought(monkeypatch):
    coord = Coordinator()
    proc = Processor(coord)
    proc.set_state(AgentState.WAKEUP)

    thought = Thought(
        thought_id="t1",
        source_task_id="wakeup",
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at="0",
        updated_at="0",
        round_number=0,
        content="hi",
    )
    proc.add_thought(thought)

    called = {}

    async def fake_process(th: Thought):
        called["thought_id"] = th.thought_id
        return await Coordinator().process_thought(th)

    monkeypatch.setattr(coord, "process_thought", fake_process)

    await proc.process_round()

    assert called.get("thought_id") == "t1"
    assert thought.status == ThoughtStatus.COMPLETED
    assert thought.final_action["type"] == "speak"
