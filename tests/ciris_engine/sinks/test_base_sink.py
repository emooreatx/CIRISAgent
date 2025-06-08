import pytest
from unittest.mock import AsyncMock
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.schemas.service_actions_v1 import (
    ActionMessage,
    ActionType,
    SendMessageAction,
    SendDeferralAction,
)

class DummySink(MultiServiceActionSink):
    async def _get_service(self, service_type: str, action: ActionMessage):
        return None

@pytest.mark.asyncio
async def test_enqueue_action_queue_full():
    sink = DummySink(max_queue_size=1)
    msg = ActionMessage(ActionType.SEND_MESSAGE, "handler", {})
    assert await sink.enqueue_action(msg) is True
    assert await sink.enqueue_action(msg) is False

@pytest.mark.asyncio
async def test_process_action_calls_fallback(monkeypatch):
    sink = DummySink()
    fallback = AsyncMock()
    monkeypatch.setattr(sink, "_handle_fallback", fallback)
    msg = SendMessageAction("h", {}, channel_id="c", content="hi")
    await sink._process_action(msg)
    fallback.assert_awaited_once()

@pytest.mark.asyncio
async def test_validate_action_rules():
    sink = DummySink()
    msg = SendMessageAction("h", {}, channel_id="", content="")
    assert await sink._validate_action(msg) is False
    def_msg = SendDeferralAction("h", {}, thought_id="", reason="")
    assert await sink._validate_action(def_msg) is False

