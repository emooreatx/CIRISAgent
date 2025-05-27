import uuid
from datetime import datetime, timezone
import pytest

from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.dma.dma_executor import run_dma_with_retries


def make_thought() -> Thought:
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id="task1",
        thought_type="seed",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=0,
        content="test",
        priority=1,
    )


@pytest.mark.asyncio
async def test_run_dma_with_retries_success_after_retries():
    thought = make_thought()
    call_count = {"n": 0}

    async def sometimes_fail(t):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise Exception("boom")
        return "ok"

    result = await run_dma_with_retries(sometimes_fail, thought, retry_limit=3)
    assert result == "ok"
    assert call_count["n"] == 3
    assert thought.escalations == []


@pytest.mark.asyncio
async def test_run_dma_with_retries_escalates_after_limit():
    thought = make_thought()

    async def always_fail(t):
        raise Exception("fail")

    result = await run_dma_with_retries(always_fail, thought, retry_limit=2)
    assert result is thought
    assert thought.status == ThoughtStatus.DEFERRED
    assert len(thought.escalations) == 1
    assert thought.escalations[0]["type"] == "dma_failure"

