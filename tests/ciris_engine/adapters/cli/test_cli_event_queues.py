import pytest
import asyncio
from ciris_engine.adapters.cli.cli_event_queues import (
    CLIPassiveObserveQueue, CLIActiveObserveQueue, CLIFeedbackQueue
)

@pytest.mark.asyncio
@pytest.mark.parametrize("QueueClass", [
    CLIPassiveObserveQueue, CLIActiveObserveQueue, CLIFeedbackQueue
])
async def test_enqueue_dequeue(QueueClass):
    queue = QueueClass()
    assert queue.empty()
    await queue.enqueue("event1")
    assert not queue.empty()
    result = await queue.dequeue()
    assert result == "event1"
    assert queue.empty()

@pytest.mark.asyncio
@pytest.mark.parametrize("QueueClass", [
    CLIPassiveObserveQueue, CLIActiveObserveQueue, CLIFeedbackQueue
])
async def test_enqueue_nowait(QueueClass):
    queue = QueueClass()
    assert queue.empty()
    queue.enqueue_nowait("event2")
    assert not queue.empty()
    result = await queue.dequeue()
    assert result == "event2"
    assert queue.empty()

@pytest.mark.asyncio
@pytest.mark.parametrize("QueueClass", [
    CLIPassiveObserveQueue, CLIActiveObserveQueue, CLIFeedbackQueue
])
async def test_queue_maxsize(QueueClass):
    queue = QueueClass(maxsize=1)
    await queue.enqueue("a")
    with pytest.raises(asyncio.QueueFull):
        queue.enqueue_nowait("b")
    # Dequeue to make space
    await queue.dequeue()
    queue.enqueue_nowait("c")
    assert not queue.empty()
    assert await queue.dequeue() == "c"
    assert queue.empty()
