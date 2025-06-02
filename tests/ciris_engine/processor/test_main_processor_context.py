import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states import AgentState
from ciris_engine.utils.context_utils import build_dispatch_context

@pytest.mark.asyncio
@pytest.mark.parametrize("agent_mode,task_channel_id,expected_channel_id,expected_origin_service", [
    ("cli", "CLI", "CLI", "CLI"),
    ("cli", "cli_startup", "cli_startup", "CLI"),
    ("discord", "default", "default", "discord"),
    ("discord", "discord_startup", "discord_startup", "discord"),
    ("discord", "12345", "12345", "discord"),
    ("cli", "67890", "67890", "CLI"),
])
async def test_build_dispatch_context_modes(agent_mode, task_channel_id, expected_channel_id, expected_origin_service, monkeypatch):
    from ciris_engine.schemas.config_schemas_v1 import AgentProfile
    
    # Minimal AppConfig mock
    app_config = MagicMock()
    app_config.agent_mode = agent_mode
    active_profile = AgentProfile(name="test_profile")
    dispatcher = MagicMock()
    services = {}
    processor = AgentProcessor(
        app_config=app_config,
        active_profile=active_profile,  # Pass active profile
        thought_processor=MagicMock(),
        action_dispatcher=dispatcher,
        services=services,
        startup_channel_id=None
    )
    # Create a fake thought and task
    thought = MagicMock(spec=Thought)
    thought.thought_id = "th1"
    thought.source_task_id = "task1"
    task = MagicMock(spec=Task)
    task.context = {"channel_id": task_channel_id}
    # Build context using centralized utility
    context = build_dispatch_context(
        thought=thought, 
        task=task, 
        app_config=app_config, 
        startup_channel_id=None, 
        round_number=0
    )
    assert context["channel_id"] == str(expected_channel_id)
    assert context["origin_service"] == expected_origin_service
    assert context["thought_id"] == "th1"
    assert context["source_task_id"] == "task1"
    assert "round_number" in context
