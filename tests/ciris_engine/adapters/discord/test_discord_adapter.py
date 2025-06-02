import pytest
import asyncio
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter

@pytest.mark.asyncio
async def test_discord_adapter_initialization():
    """Test that DiscordAdapter can be initialized without a queue."""
    adapter = DiscordAdapter("fake_token")

    assert adapter.token == "fake_token"
    assert adapter.client is None
