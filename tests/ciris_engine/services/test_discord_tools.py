import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.services import discord_tools

@pytest.mark.asyncio
async def test_discord_delete_message_success():
    bot = MagicMock()
    channel = AsyncMock()
    bot.get_channel.return_value = channel
    channel.fetch_message.return_value = AsyncMock()
    await discord_tools.discord_delete_message(bot, 1, 2)
    bot.get_channel.assert_called_with(1)
    channel.fetch_message.assert_called_with(2)

@pytest.mark.asyncio
async def test_discord_delete_message_failure():
    bot = MagicMock()
    bot.get_channel.side_effect = Exception("fail")
    result = await discord_tools.discord_delete_message(bot, 1, 2)
    assert result.execution_status.name in ("FAILED", "FAILURE")
