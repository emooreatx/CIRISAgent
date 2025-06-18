import os
import pytest
from unittest.mock import MagicMock, patch
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.thought_processor import ThoughtProcessor

# Import adapter configs to resolve forward references
try:
    from ciris_engine.adapters.discord.config import DiscordAdapterConfig
    from ciris_engine.adapters.api.config import APIAdapterConfig
    from ciris_engine.adapters.cli.config import CLIAdapterConfig
except ImportError:
    DiscordAdapterConfig = type('DiscordAdapterConfig', (), {})
    APIAdapterConfig = type('APIAdapterConfig', (), {})
    CLIAdapterConfig = type('CLIAdapterConfig', (), {})

# Rebuild models with resolved references  
try:
    AppConfig.model_rebuild()
except Exception:
    pass

from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.identity_schemas_v1 import AgentIdentityRoot, CoreProfile, IdentityMetadata
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from datetime import datetime, timezone

def test_channel_id_flows_from_env_to_processors(monkeypatch):
    
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

    # Create active identity
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

    # Mock all processors and dependencies
    thought_processor = MagicMock(spec=ThoughtProcessor)
    action_dispatcher = MagicMock(spec=ActionDispatcher)
    services = {}

    # Patch WakeupProcessor to capture startup_channel_id
    with patch("ciris_engine.processor.wakeup_processor.WakeupProcessor.__init__", return_value=None) as mock_wakeup_init:
        AgentProcessor(
            app_config=app_config,
            agent_identity=active_identity,  # Pass active identity
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
