import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.states import AgentState
from ciris_engine.utils.context_utils import build_dispatch_context

@pytest.mark.asyncio
@pytest.mark.parametrize("agent_mode,startup_channel_id,task_channel_id,expected_channel_id,expected_origin_service", [
    ("cli", None, None, "CLI", "CLI"),
    ("cli", "cli_startup", None, "cli_startup", "CLI"),
    ("discord", None, None, "default", "discord"),
    ("discord", "discord_startup", None, "discord_startup", "discord"),
    ("discord", None, "12345", "12345", "discord"),
    ("cli", None, "67890", "67890", "CLI"),
])
async def test_build_dispatch_context_modes(agent_mode, startup_channel_id, task_channel_id, expected_channel_id, expected_origin_service):
    # Minimal AppConfig mock
    app_config = MagicMock()
    app_config.agent_mode = agent_mode
    # Minimal dispatcher and services
    dispatcher = MagicMock()
    services = {}
    processor = AgentProcessor(
        app_config=app_config,
        thought_processor=MagicMock(),
        action_dispatcher=dispatcher,
        services=services,
        startup_channel_id=startup_channel_id
    )
    # Create a fake thought and task
    thought = MagicMock(spec=Thought)
    thought.thought_id = "th1"
    thought.source_task_id = "task1"
    task = MagicMock(spec=Task)
    task.context = {}
    if task_channel_id is not None:
        task.context["channel_id"] = task_channel_id
    # Build context using centralized utility
    context = build_dispatch_context(
        thought=thought, 
        task=task, 
        app_config=app_config, 
        startup_channel_id=startup_channel_id, 
        round_number=0
    )
    assert context["channel_id"] == str(expected_channel_id)
    assert context["origin_service"] == expected_origin_service
    assert context["thought_id"] == "th1"
    assert context["source_task_id"] == "task1"
    assert "round_number" in context

@pytest.mark.asyncio
async def test_build_dispatch_context_missing_everything_logs_error(caplog):
    app_config = MagicMock()
    app_config.agent_mode = "discord"
    dispatcher = MagicMock()
    services = {}
    processor = AgentProcessor(
        app_config=app_config,
        thought_processor=MagicMock(),
        action_dispatcher=dispatcher,
        services=services,
        startup_channel_id=None
    )
    thought = MagicMock(spec=Thought)
    thought.thought_id = "th2"
    thought.source_task_id = "task2"
    task = MagicMock(spec=Task)
    task.context = {}
    with caplog.at_level("ERROR"):
        context = build_dispatch_context(
            thought=thought, 
            task=task, 
            app_config=app_config, 
            startup_channel_id=None, 
            round_number=0
        )
    assert context["channel_id"] == "default"
    assert "No channel_id found for thought th2 and no startup_channel_id set" in caplog.text
