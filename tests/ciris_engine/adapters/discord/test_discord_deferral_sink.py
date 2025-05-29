import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.adapters.discord.discord_deferral_sink import DiscordDeferralSink
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter

@pytest.mark.asyncio
async def test_discord_deferral_sink_send_deferral_get_channel_found():
    mock_adapter = MagicMock(spec=DiscordAdapter)
    mock_client = MagicMock()
    mock_adapter.client = mock_client
    channel = AsyncMock()
    mock_client.get_channel.return_value = channel
    mock_client.fetch_channel = AsyncMock()
    channel.send = AsyncMock()
    mock_client.wait_until_ready = AsyncMock()
    sink = DiscordDeferralSink(mock_adapter, deferral_channel_id="42")
    await sink.send_deferral(
        task_id="t1",
        thought_id="th1",
        reason="Test reason",
        package={"user_nick": "tester", "channel": "chan", "metadata": {"foo": "bar"}}
    )
    channel.send.assert_awaited()
    mock_client.get_channel.assert_called_with(42)
    mock_client.fetch_channel.assert_not_awaited()

@pytest.mark.asyncio
async def test_discord_deferral_sink_send_deferral_get_channel_none():
    mock_adapter = MagicMock(spec=DiscordAdapter)
    mock_client = MagicMock()
    mock_adapter.client = mock_client
    mock_client.get_channel.return_value = None
    channel = AsyncMock()
    mock_client.fetch_channel = AsyncMock(return_value=channel)
    channel.send = AsyncMock()
    mock_client.wait_until_ready = AsyncMock()
    sink = DiscordDeferralSink(mock_adapter, deferral_channel_id="42")
    await sink.send_deferral(
        task_id="t1",
        thought_id="th1",
        reason="Test reason",
        package={"user_nick": "tester", "channel": "chan", "metadata": {"foo": "bar"}}
    )
    channel.send.assert_awaited()
    mock_client.get_channel.assert_called_with(42)
    mock_client.fetch_channel.assert_awaited_with(42)
