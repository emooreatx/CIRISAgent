import pytest
from unittest.mock import AsyncMock

from ciris_engine.adapters.base_observer import BaseObserver
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

class DummyObserver(BaseObserver[IncomingMessage]):
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

@pytest.mark.asyncio
async def test_process_message_secrets():
    mock_service = AsyncMock()

    async def proc(text: str, context_hint: str = "", source_message_id: str | None = None):
        ref = AsyncMock()
        ref.secret_uuid = "uuid"
        ref.context_hint = "hint"
        ref.sensitivity = "HIGH"
        return "clean", [ref]

    mock_service.process_incoming_text.side_effect = proc

    obs = DummyObserver(lambda _: None, secrets_service=mock_service, origin_service="test")
    msg = IncomingMessage(message_id="1", content="secret", author_id="a", author_name="A", channel_id="c")
    processed = await obs._process_message_secrets(msg)
    assert processed.content == "clean"
    assert processed._detected_secrets[0]["uuid"] == "uuid"

@pytest.mark.asyncio
async def test_apply_message_filtering_no_service():
    obs = DummyObserver(lambda _: None, origin_service="test")
    msg = IncomingMessage(message_id="1", content="hi", author_id="a", author_name="A", channel_id="c")
    res = await obs._apply_message_filtering(msg, "cli")
    assert res.should_process

@pytest.mark.asyncio
async def test_add_to_feedback_queue():
    sink = AsyncMock()
    sink.send_message.return_value = True
    obs = DummyObserver(lambda _: None, multi_service_sink=sink, origin_service="test")
    msg = IncomingMessage(message_id="1", content="hello", author_id="a", author_name="A", channel_id="c")
    await obs._add_to_feedback_queue(msg)
    sink.send_message.assert_awaited_once()
