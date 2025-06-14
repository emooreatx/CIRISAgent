import os
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.live
@pytest.mark.asyncio
async def test_discord_runtime_service_registry_live():
    """Connect to Discord and verify handler service registrations."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    channel = os.getenv("DISCORD_CHANNEL_ID")
    if not token or not channel:
        pytest.skip("Discord credentials not provided")

    try:
        runtime = CIRISRuntime(adapter_types=["discord"], profile_name="default", discord_bot_token=token, startup_channel_id=channel)
    except RuntimeError as e:
        if "No valid adapters specified" in str(e):
            pytest.skip("Discord adapter not available or failed to load")
        raise
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
