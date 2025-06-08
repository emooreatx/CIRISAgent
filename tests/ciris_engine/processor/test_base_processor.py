import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.processor.base_processor import BaseProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, ThoughtType


class DummyProcessor(BaseProcessor):
    def get_supported_states(self):
        return [AgentState.WORK]

    async def can_process(self, state: AgentState) -> bool:
        return True

    async def process(self, round_number: int):
        return {}


def make_thought():
    return Thought(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="hello",
    )


@pytest.mark.asyncio
async def test_dispatch_action_success():
    ad = AsyncMock()
    tp = AsyncMock()
    proc = DummyProcessor(AppConfig(), tp, ad, {})

    result = object()
    thought = object()
    ctx = {"a": 1}

    assert await proc.dispatch_action(result, thought, ctx)
    ad.dispatch.assert_awaited_with(action_selection_result=result, thought=thought, dispatch_context=ctx)
    assert proc.metrics["errors"] == 0


@pytest.mark.asyncio
async def test_dispatch_action_failure():
    ad = AsyncMock()
    ad.dispatch.side_effect = Exception("boom")
    tp = AsyncMock()
    proc = DummyProcessor(AppConfig(), tp, ad, {})

    ok = await proc.dispatch_action(object(), object(), {})
    assert not ok
    assert proc.metrics["errors"] == 1


@pytest.mark.asyncio
async def test_process_thought_item_updates_metrics():
    ad = AsyncMock()
    tp = AsyncMock()
    proc = DummyProcessor(AppConfig(), tp, ad, {})

    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        content=ThoughtContent(text="hello"),
    )

    tp.process_thought = AsyncMock(return_value="r")

    result = await proc.process_thought_item(item)
    assert result == "r"
    assert proc.metrics["items_processed"] == 1


@pytest.mark.asyncio
async def test_process_thought_item_error(monkeypatch):
    ad = AsyncMock()
    tp = AsyncMock()
    tp.process_thought = AsyncMock(side_effect=Exception("err"))
    proc = DummyProcessor(AppConfig(), tp, ad, {})

    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        content=ThoughtContent(text="hello"),
    )

    with pytest.raises(Exception):
        await proc.process_thought_item(item)
    assert proc.metrics["errors"] == 1


@pytest.mark.asyncio
async def test_process_thought_item_dma_failure_fallback(monkeypatch):
    ad = AsyncMock()
    tp = AsyncMock()
    proc = DummyProcessor(AppConfig(), tp, ad, {})

    # Patch force_ponder and force_defer to track calls
    proc.force_ponder = AsyncMock(return_value="pondered")
    proc.force_defer = AsyncMock(return_value="deferred")

    class DMAFailure(Exception):
        is_dma_failure = True

    # Simulate DMA failure
    tp.process_thought = AsyncMock(side_effect=DMAFailure("dma fail"))

    from ciris_engine.processor.processing_queue import ThoughtContent
    item = ProcessingQueueItem(
        thought_id="th1",
        source_task_id="t1",
        thought_type=ThoughtType.STANDARD,
        content=ThoughtContent(text="hello"),
    )

    # Should call force_ponder and return its result
    result = await proc.process_thought_item(item)
    proc.force_ponder.assert_awaited_once_with(item, None)
    assert result == "pondered"
    # Should not call force_defer
    proc.force_defer.assert_not_called()
