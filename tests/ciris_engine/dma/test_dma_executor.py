import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.dma.dma_executor import (
    run_dma_with_retries,
    run_pdma,
    run_csdma,
    run_dsdma,
    run_action_selection_pdma,
    DMAFailure,
)
from ciris_engine.processor.processing_queue import ProcessingQueueItem

@pytest.mark.asyncio
async def test_run_dma_with_retries_success():
    async def fn(x): return x + 1
    result = await run_dma_with_retries(fn, 1, retry_limit=2, timeout_seconds=0.5)
    assert result == 2

@pytest.mark.asyncio
async def test_run_dma_with_retries_failure():
    async def fn(x): raise ValueError("fail")
    with pytest.raises(DMAFailure):
        await run_dma_with_retries(fn, 1, retry_limit=1, timeout_seconds=0.5)


@pytest.mark.asyncio
async def test_run_dma_with_retries_timeout():
    async def fn(x):
        await asyncio.sleep(0.2)
        return x

    with pytest.raises(DMAFailure):
        await run_dma_with_retries(fn, 1, retry_limit=1, timeout_seconds=0.1)

@pytest.mark.asyncio
async def test_run_pdma():
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value="ok")
    from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
    ctx = ThoughtContext(system_snapshot=SystemSnapshot())
    item = Thought(
        thought_id="t1",
        source_task_id="task1",
        thought_type="test",
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="c",
        context=ctx,
    )
    result = await run_pdma(evaluator, item, context=ctx)
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_pdma_queue_item_context_fallback():
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value="ok")
    from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
    ctx = ThoughtContext(system_snapshot=SystemSnapshot())
    thought = Thought(
        thought_id="t2",
        source_task_id="task2",
        thought_type="test",
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="c",
        context=None,
    )
    item = ProcessingQueueItem.from_thought(thought, initial_ctx=ctx.model_dump())
    result = await run_pdma(evaluator, item, context=None)
    evaluator.evaluate.assert_awaited_with(item, context=ctx)
    assert result == "ok"


@pytest.mark.asyncio
async def test_run_pdma_invalid_context_raises():
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value="ok")
    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="t3",
        source_task_id="task3",
        thought_type="test",
        content=ThoughtContent(text="c"),
    )
    with pytest.raises(DMAFailure):
        await run_pdma(evaluator, item)

@pytest.mark.asyncio
async def test_run_csdma():
    evaluator = MagicMock()
    evaluator.evaluate_thought = AsyncMock(return_value="ok")
    result = await run_csdma(evaluator, "item")
    assert result == "ok"

@pytest.mark.asyncio
async def test_run_dsdma():
    dsdma = MagicMock()
    dsdma.evaluate_thought = AsyncMock(return_value="ok")
    result = await run_dsdma(dsdma, "item")
    assert result == "ok"

@pytest.mark.asyncio
async def test_run_action_selection_pdma():
    evaluator = MagicMock()
    evaluator.evaluate = AsyncMock(return_value="ok")
    result = await run_action_selection_pdma(evaluator, {"foo": "bar"})
    assert result == "ok"
