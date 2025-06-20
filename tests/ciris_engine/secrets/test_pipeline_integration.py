"""
Test suite for secrets message pipeline integration.

Tests the end-to-end flow of secrets detection in message processing pipeline.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from ciris_engine.adapters.discord.discord_observer import DiscordObserver
from ciris_engine.adapters.cli.cli_observer import CLIObserver
from ciris_engine.adapters.api.api_observer import APIObserver
from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage, IncomingMessage
from ciris_engine.secrets.service import SecretsService
from ciris_engine.action_handlers.base_handler import BaseActionHandler, ActionHandlerDependencies
from ciris_engine.message_buses.bus_manager import BusManager
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.context.builder import ContextBuilder


@pytest.fixture
def mock_secrets_service():
    """Mock SecretsService for testing."""
    service = AsyncMock(spec=SecretsService)
    
    # Mock process_incoming_text to return detected secrets
    async def mock_process_text(text, context_hint="", source_message_id=None):
        if "sk-1234567890" in text:
            # Simulate detecting an API key
            processed_text = text.replace("sk-1234567890", "SECRET_550e8400-e29b-41d4-a716-446655440000")
            mock_ref = MagicMock()
            mock_ref.secret_uuid = "550e8400-e29b-41d4-a716-446655440000"
            mock_ref.context_hint = "API Key"
            mock_ref.sensitivity = "HIGH"
            return processed_text, [mock_ref]
        return text, []
    
    service.process_incoming_text.side_effect = mock_process_text
    return service


@pytest.mark.asyncio
class TestMessagePipelineIntegration:
    """Test secrets integration in message processing pipeline."""
    
    async def test_discord_observer_processes_secrets(self, mock_secrets_service):
        """Test that DiscordObserver detects and processes secrets in messages."""
        observer = DiscordObserver(
            monitored_channel_ids=["test_channel"],
            secrets_service=mock_secrets_service
        )
        
        # Create message with secret
        original_msg = DiscordMessage(
            message_id="test_msg_1",
            content="Here's my API key: sk-1234567890",
            author_id="user123",
            author_name="TestUser",
            channel_id="test_channel",
            timestamp=datetime.now().isoformat(),
            is_bot=False,
            guild_id="test_guild"
        )
        
        # Process through secrets detection
        processed_msg = await observer._process_message_secrets(original_msg)
        
        # Verify secret was detected and replaced
        assert "sk-1234567890" not in processed_msg.content
        assert "SECRET_550e8400-e29b-41d4-a716-446655440000" in processed_msg.content
        assert hasattr(processed_msg, '_detected_secrets')
        assert len(processed_msg._detected_secrets) == 1
        assert processed_msg._detected_secrets[0]["uuid"] == "550e8400-e29b-41d4-a716-446655440000"
        
        # Verify service was called correctly
        mock_secrets_service.process_incoming_text.assert_called_once()
        call_args = mock_secrets_service.process_incoming_text.call_args
        assert call_args[0][0] == "Here's my API key: sk-1234567890"
        
    async def test_cli_observer_processes_secrets(self, mock_secrets_service):
        """Test that CLIObserver detects and processes secrets in messages."""
        mock_on_observe = AsyncMock()
        observer = CLIObserver(
            on_observe=mock_on_observe,
            secrets_service=mock_secrets_service,
            interactive=False
        )
        
        # Create message with secret
        original_msg = IncomingMessage(
            message_id="cli_msg_1",
            content="My password is sk-1234567890",
            author_id="local_user",
            author_name="User",
            channel_id="cli"
        )
        
        # Process through secrets detection
        processed_msg = await observer._process_message_secrets(original_msg)
        
        # Verify secret was detected and replaced
        assert "sk-1234567890" not in processed_msg.content
        assert "SECRET_550e8400-e29b-41d4-a716-446655440000" in processed_msg.content
        assert hasattr(processed_msg, '_detected_secrets')
        assert len(processed_msg._detected_secrets) == 1
        
    async def test_api_observer_processes_secrets(self, mock_secrets_service):
        """Test that APIObserver detects and processes secrets in messages."""
        mock_on_observe = AsyncMock()
        observer = APIObserver(
            on_observe=mock_on_observe,
            secrets_service=mock_secrets_service
        )
        
        # Create message with secret
        original_msg = IncomingMessage(
            message_id="api_msg_1",
            content="Token: sk-1234567890",
            author_id="api_user",
            author_name="API User",
            channel_id="api"
        )
        
        # Process through secrets detection
        processed_msg = await observer._process_message_secrets(original_msg)
        
        # Verify secret was detected and replaced
        assert "sk-1234567890" not in processed_msg.content
        assert "SECRET_550e8400-e29b-41d4-a716-446655440000" in processed_msg.content
        assert hasattr(processed_msg, '_detected_secrets')
        assert len(processed_msg._detected_secrets) == 1


@pytest.mark.asyncio
class TestActionHandlerSecrets:
    """Test secrets decapsulation in action handlers."""
    
    async def test_base_handler_decapsulates_secrets(self):
        """Test that BaseActionHandler can decapsulate secrets from parameters."""
        # Mock dependencies with secrets service
        mock_secrets_service = AsyncMock()
        
        def mock_decapsulate(text, action_type=None, context=None, context_hint=None):
            # Only decapsulate for allowed action types (simulate real logic)
            allowed_actions = ["tool", "speak", "memorize"]
            # Extract action from context_hint if action_type not provided
            if not action_type and context_hint:
                # context_hint is like "speak_params" - extract the action
                action_type = context_hint.split('_')[0] if '_' in context_hint else None
            
            def recursive_decapsulate(obj):
                if isinstance(obj, str):
                    if action_type in allowed_actions:
                        return obj.replace("SECRET_550e8400-e29b-41d4-a716-446655440000", "sk-1234567890")
                    return obj
                elif isinstance(obj, dict):
                    return {k: recursive_decapsulate(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [recursive_decapsulate(i) for i in obj]
                else:
                    return obj
            return recursive_decapsulate(text)
        
        # Create wrapper that accepts the expected parameters
        async def mock_decapsulate_secrets_in_parameters(parameters, **kwargs):
            # Extract action_type from kwargs
            action_type = kwargs.get('action_type', 'speak')
            return mock_decapsulate(parameters, action_type=action_type)
        
        mock_secrets_service.decapsulate_secrets.side_effect = mock_decapsulate
        mock_secrets_service.decapsulate_secrets_in_parameters.side_effect = mock_decapsulate_secrets_in_parameters
        
        mock_service_registry = AsyncMock()
        bus_manager = BusManager(mock_service_registry)
        dependencies = ActionHandlerDependencies(bus_manager=bus_manager, secrets_service=mock_secrets_service)
        
        # Create a test handler
        class TestHandler(BaseActionHandler):
            async def handle(self, result, thought, dispatch_context):
                pass
        
        handler = TestHandler(dependencies)
        
        # Create action result with secret reference
        original_result = ActionSelectionResult(
            selected_action="speak",
            action_parameters={
                "content": "Here's the key: SECRET_550e8400-e29b-41d4-a716-446655440000",
                "channel_id": "test"
            },
            rationale="Testing",
            confidence=0.9
        )
        
        # Process through secrets decapsulation
        processed_result = await handler._decapsulate_secrets_in_params(original_result, "speak")
        
        # Debug print
        print(f"Original: {original_result.action_parameters}")
        print(f"Processed: {processed_result.action_parameters}")
        
        # Verify secret was decapsulated
        assert "SECRET_550e8400-e29b-41d4-a716-446655440000" not in str(processed_result.action_parameters)
        assert "sk-1234567890" in processed_result.action_parameters["content"]
        
        # Verify service was called
        mock_secrets_service.decapsulate_secrets_in_parameters.assert_called_once()


@pytest.mark.asyncio 
class TestContextBuilderSecrets:
    """Test secrets integration in context builder."""
    
    async def test_context_builder_includes_secrets_snapshot(self):
        """Test that ContextBuilder includes secrets information in SystemSnapshot."""
        # Mock secrets service
        mock_secrets_service = AsyncMock()
        
        # Mock store with secrets
        mock_store = AsyncMock()
        from ciris_engine.schemas.secrets_schemas_v1 import SecretReference
        mock_secret = SecretReference(
            uuid="test-uuid",
            description="Test secret",
            context_hint="Test API key",
            sensitivity="HIGH",
            detected_pattern="api_key",
            auto_decapsulate_actions=[],
            created_at=datetime.now(),
            last_accessed=None
        )
        mock_store.list_all_secrets.return_value = [mock_secret]
        mock_secrets_service.store = mock_store
        
        # Mock filter
        mock_filter = AsyncMock()
        mock_config = MagicMock()
        mock_config.version = 1
        mock_filter.get_filter_config.return_value = mock_config
        mock_secrets_service.filter = mock_filter
        
        # Create context builder
        builder = ContextBuilder(secrets_service=mock_secrets_service)
        
        # Build secrets snapshot
        secrets_data = await builder._build_secrets_snapshot()
        
        # Verify secrets data is included
        assert "detected_secrets" in secrets_data
        assert "secrets_filter_version" in secrets_data
        assert "total_secrets_stored" in secrets_data
        
        assert len(secrets_data["detected_secrets"]) == 1
        assert secrets_data["secrets_filter_version"] == 1
        assert secrets_data["total_secrets_stored"] == 1
        
        # Verify SecretReference structure
        secret_ref = secrets_data["detected_secrets"][0]
        assert secret_ref.uuid == "test-uuid"
        assert secret_ref.description == "Test secret"
        assert secret_ref.sensitivity == "HIGH"


@pytest.mark.asyncio
class TestEndToEndFlow:
    """Test complete end-to-end secrets flow."""
    
    async def test_message_to_action_secrets_flow(self, mock_secrets_service):
        """Test secrets flow from message processing to action execution."""
        # Setup: Message contains secret
        observer = DiscordObserver(
            monitored_channel_ids=["test_channel"],
            secrets_service=mock_secrets_service
        )
        
        original_msg = DiscordMessage(
            message_id="test_msg",
            content="Use this key: sk-1234567890",
            author_id="user123",
            author_name="TestUser", 
            channel_id="test_channel",
            timestamp=datetime.now().isoformat(),
            is_bot=False,
            guild_id="test_guild"
        )
        
        # Step 1: Message processing detects and replaces secret
        processed_msg = await observer._process_message_secrets(original_msg)
        
        assert "SECRET_550e8400-e29b-41d4-a716-446655440000" in processed_msg.content
        assert len(processed_msg._detected_secrets) == 1
        
        # Step 2: Later action handler can decapsulate the secret when needed
        mock_decap_service = AsyncMock()
        def recursive_decapsulate(obj):
            if isinstance(obj, str):
                return obj.replace("SECRET_550e8400-e29b-41d4-a716-446655440000", "sk-1234567890")
            elif isinstance(obj, dict):
                return {k: recursive_decapsulate(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [recursive_decapsulate(i) for i in obj]
            else:
                return obj

        def mock_decapsulate(text, action_type=None, context=None, context_hint=None):
            # Only decapsulate for allowed action types (simulate real logic)
            allowed_actions = ["tool", "speak", "memorize"]
            # Extract action from context_hint if action_type not provided
            if not action_type and context_hint:
                # context_hint is like "tool_params" - extract the action
                action_type = context_hint.split('_')[0] if '_' in context_hint else None
            
            def recursive_decapsulate(obj):
                if isinstance(obj, str):
                    if action_type in allowed_actions:
                        return obj.replace("SECRET_550e8400-e29b-41d4-a716-446655440000", "sk-1234567890")
                    return obj
                elif isinstance(obj, dict):
                    return {k: recursive_decapsulate(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [recursive_decapsulate(i) for i in obj]
                else:
                    return obj
            return recursive_decapsulate(text)
        # Create wrapper that accepts the expected parameters
        async def mock_decapsulate_secrets_in_parameters(parameters, **kwargs):
            # Extract action_type from kwargs
            action_type = kwargs.get('action_type', 'tool')
            return mock_decapsulate(parameters, action_type=action_type)
        
        mock_decap_service.decapsulate_secrets.side_effect = mock_decapsulate
        mock_decap_service.decapsulate_secrets_in_parameters.side_effect = mock_decapsulate_secrets_in_parameters
        
        mock_service_registry = AsyncMock()
        bus_manager = BusManager(mock_service_registry)
        dependencies = ActionHandlerDependencies(bus_manager=bus_manager, secrets_service=mock_decap_service)
        
        class TestHandler(BaseActionHandler):
            async def handle(self, result, thought, dispatch_context):
                pass
        
        handler = TestHandler(dependencies)
        
        result_with_secret = ActionSelectionResult(
            selected_action="tool",
            action_parameters={
                "name": "api_call",
                "parameters": {"api_key": "SECRET_550e8400-e29b-41d4-a716-446655440000"}
            },
            rationale="Making API call",
            confidence=0.8
        )
        
        # Step 3: Action handler decapsulates secret
        processed_result = await handler._decapsulate_secrets_in_params(result_with_secret, "tool")
        
        # Verify the secret was decapsulated for use
        assert processed_result.action_parameters["parameters"]["api_key"] == "sk-1234567890"
        
        # This demonstrates the complete flow:
        # 1. Secret detected in incoming message -> replaced with UUID
        # 2. Agent processes message with UUID references 
        # 3. When action needs actual secret -> auto-decapsulated based on action type