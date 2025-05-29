import pytest
from unittest.mock import MagicMock
from ciris_engine.adapters.discord.discord_feedback_sink import DiscordFeedbackSink
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

@pytest.mark.asyncio
async def test_discord_feedback_sink_process_feedback_handles_feedback():
    mock_adapter = MagicMock(spec=DiscordAdapter)
    mock_adapter.client = MagicMock()
    sink = DiscordFeedbackSink(mock_adapter, deferral_channel_id="42")
    msg = MagicMock(spec=IncomingMessage)
    msg.channel_id = "42"
    raw_message = MagicMock()
    raw_message.reference = MagicMock()
    raw_message.reference.message_id = "123"
    raw_message.reference.resolved = MagicMock()
    raw_message.reference.resolved.content = "```json\n{\"foo\": \"bar\"}\n```"
    # Patch persistence.get_deferral_report_context and add_thought
    import ciris_engine.adapters.discord.discord_feedback_sink as feedback_mod
    feedback_mod.persistence.get_deferral_report_context = MagicMock(return_value=("task1", "th1", {"foo": "bar"}))
    feedback_mod.persistence.add_thought = MagicMock()
    feedback_mod.persistence.get_task_by_id = MagicMock(return_value=MagicMock(priority=1))
    result = await sink.process_feedback(msg, raw_message)
    assert result is True
    feedback_mod.persistence.add_thought.assert_called()

@pytest.mark.asyncio
async def test_discord_feedback_sink_process_feedback_wrong_channel():
    mock_adapter = MagicMock(spec=DiscordAdapter)
    mock_adapter.client = MagicMock()
    sink = DiscordFeedbackSink(mock_adapter, deferral_channel_id="42")
    msg = MagicMock(spec=IncomingMessage)
    msg.channel_id = "99"
    raw_message = MagicMock()
    result = await sink.process_feedback(msg, raw_message)
    assert result is False
