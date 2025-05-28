import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.services.discord_deferral_sink import DiscordDeferralSink

@pytest.mark.asyncio
async def test_send_deferral_channel_missing():
    adapter = MagicMock()
    sink = DiscordDeferralSink(adapter, None)
    await sink.send_deferral("tid", "thid", "reason", {})
    # Should log a warning and return without error
