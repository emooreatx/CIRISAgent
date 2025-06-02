import os
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ciris_engine.runtime.discord_runtime import DiscordRuntime


@pytest.mark.live
@pytest.mark.asyncio
async def test_discord_runtime_service_registry_live():
    """Connect to Discord and verify handler service registrations."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel = os.getenv("DISCORD_CHANNEL_ID")
    if not token or not channel:
        pytest.skip("Discord credentials not provided")

    runtime = DiscordRuntime(token=token, startup_channel_id=channel)
    await runtime.initialize()

    info = runtime.service_registry.get_provider_info()
    handlers = info.get("handlers", {})

    expected_handlers = [
        "SpeakHandler",
        "ObserveHandler",
        "ToolHandler",
        "DeferHandler",
        "MemorizeHandler",
        "RecallHandler",
        "TaskCompleteHandler",
    ]

    for handler in expected_handlers:
        assert handler in handlers, f"{handler} missing in registry"

    await runtime.shutdown()
