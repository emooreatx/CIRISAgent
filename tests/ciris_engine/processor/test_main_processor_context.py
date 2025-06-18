import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot, CoreProfile, IdentityMetadata
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.utils.context_utils import build_dispatch_context
from datetime import datetime, timezone

# Import adapter configs to resolve forward references
from ciris_engine.adapters.discord.config import DiscordAdapterConfig
from ciris_engine.adapters.api.config import APIAdapterConfig
from ciris_engine.adapters.cli.config import CLIAdapterConfig

# Rebuild models with resolved references  
AppConfig.model_rebuild()

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
    # Minimal AppConfig mock
    app_config = MagicMock()
    app_config.agent_mode = agent_mode
    active_identity = AgentIdentityRoot(
        agent_id="test_agent",
        identity_hash="test_hash_123",
        core_profile=CoreProfile(
            description="Test agent for unit tests",
            role_description="A minimal test agent profile",
            domain_specific_knowledge={},
            dsdma_prompt_template=None,
            csdma_overrides={},
            action_selection_pdma_overrides={},
            last_shutdown_memory=None
        ),
        identity_metadata=IdentityMetadata(
            created_at=datetime.now(timezone.utc).isoformat(),
            last_modified=datetime.now(timezone.utc).isoformat(),
            modification_count=0,
            creator_agent_id="system",
            lineage_trace=["system"],
            approval_required=False,
            approved_by=None,
            approval_timestamp=None
        ),
        permitted_actions=[
            HandlerActionType.OBSERVE,
            HandlerActionType.SPEAK,
            HandlerActionType.PONDER,
            HandlerActionType.DEFER,
            HandlerActionType.REJECT,
            HandlerActionType.TASK_COMPLETE
        ],
        restricted_capabilities=[]
    )
    dispatcher = MagicMock()
    services = {}
    processor = AgentProcessor(
        app_config=app_config,
        agent_identity=active_identity,  # Pass active identity
        thought_processor=MagicMock(),
        action_dispatcher=dispatcher,
        services=services,
        startup_channel_id=expected_channel_id
    )
    # Create a fake thought and task
    thought = MagicMock(spec=Thought)
    thought.thought_id = "th1"
    thought.source_task_id = "task1"
    task = MagicMock(spec=Task)
    task.task_id = "task1"
    task.context = {"channel_id": task_channel_id, "author_id": "test_user", "author_name": "Test User"}
    # Build context using centralized utility
    context = build_dispatch_context(
        thought=thought, 
        task=task, 
        app_config=app_config, 
        round_number=0
    )
    assert context.channel_context.channel_id == str(expected_channel_id)
    assert context.origin_service == expected_origin_service
    assert context.thought_id == "th1"
    assert context.source_task_id == "task1"
    assert context.round_number == 0
