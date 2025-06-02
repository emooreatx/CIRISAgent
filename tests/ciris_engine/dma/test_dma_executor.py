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
    result = await run_pdma(evaluator, "item")
    assert result == "ok"

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
