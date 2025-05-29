import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.adapters.discord.discord_observer import DiscordObserver

@pytest.mark.asyncio
async def test_handle_incoming_message_skips_non_incoming():
    observer = DiscordObserver(lambda x: None, MagicMock())
    await observer.handle_incoming_message("not_a_msg")
    # Should log a warning and return
