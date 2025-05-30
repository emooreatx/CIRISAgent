import os
import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher

def test_channel_id_flows_from_env_to_processors(monkeypatch):
    from ciris_engine.schemas.config_schemas_v1 import AgentProfile
    
    # Set up environment variable
    test_channel_id = "TEST_CHANNEL_123"
    monkeypatch.setenv("DISCORD_CHANNEL_ID", test_channel_id)

    # Mock AppConfig to reflect env var
    app_config = MagicMock(spec=AppConfig)
    app_config.cirisnode = MagicMock()
    app_config.cirisnode.base_url = "https://localhost:8001"
    app_config.agent_profiles = {}
    app_config.profile_directory = "."
    app_config.llm_services = MagicMock()
    app_config.guardrails = MagicMock()

    # Create active profile
    active_profile = AgentProfile(name="test_profile")

    # Mock all processors and dependencies
    thought_processor = MagicMock(spec=ThoughtProcessor)
    action_dispatcher = MagicMock(spec=ActionDispatcher)
    services = {}

    # Patch WakeupProcessor to capture startup_channel_id
    with patch("ciris_engine.processor.wakeup_processor.WakeupProcessor.__init__", return_value=None) as mock_wakeup_init:
        AgentProcessor(
            app_config=app_config,
            active_profile=active_profile,  # Pass active profile
            thought_processor=thought_processor,
            action_dispatcher=action_dispatcher,
            services=services,
            startup_channel_id=test_channel_id
        )
        mock_wakeup_init.assert_called()
        # Check that startup_channel_id is passed
        called_kwargs = mock_wakeup_init.call_args.kwargs
        assert called_kwargs.get("startup_channel_id") == test_channel_id

    # Also check that the environment variable is correct
    assert os.getenv("DISCORD_CHANNEL_ID") == test_channel_id
