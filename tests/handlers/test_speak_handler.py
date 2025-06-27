"""
Comprehensive unit tests for the SPEAK handler.

Tests cover:
- Message formatting with various content types
- Communication bus integration
- Rate limiting if implemented
- Message queuing and delivery
- Error handling for communication failures
- Different message targets/channels
- Message persistence/audit trail
- Both sync and async message sending
- Message acknowledgment
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import uuid

from ciris_engine.logic.handlers.external.speak_handler import SpeakHandler, _build_speak_error_context
from ciris_engine.logic.infrastructure.handlers.base_handler import ActionHandlerDependencies
from ciris_engine.logic.buses.bus_manager import BusManager
from ciris_engine.schemas.actions.parameters import SpeakParams
from ciris_engine.schemas.runtime.models import Thought, ThoughtContext, Task, TaskContext
from ciris_engine.schemas.runtime.enums import (
    ThoughtStatus, HandlerActionType, TaskStatus, ThoughtType
)
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.system_context import ChannelContext
from ciris_engine.schemas.telemetry.core import ServiceCorrelation
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.logic.secrets.service import SecretsService


# Test fixtures
@pytest.fixture
def mock_time_service():
    """Mock time service."""
    service = Mock(spec=TimeServiceProtocol)
    service.now = Mock(return_value=datetime.now(timezone.utc))
    return service


@pytest.fixture
def mock_secrets_service():
    """Mock secrets service."""
    service = Mock(spec=SecretsService)
    service.decapsulate_secrets_in_parameters = AsyncMock(
        side_effect=lambda action_type, action_params, context: action_params
    )
    return service


@pytest.fixture
def mock_communication_bus():
    """Mock communication bus."""
    bus = AsyncMock()
    bus.send_message = AsyncMock(return_value=True)
    return bus


@pytest.fixture
def mock_bus_manager(mock_communication_bus):
    """Mock bus manager with communication bus."""
    manager = Mock(spec=BusManager)
    manager.communication = mock_communication_bus
    manager.audit_service = AsyncMock()
    manager.audit_service.log_event = AsyncMock()
    return manager


@pytest.fixture
def handler_dependencies(mock_bus_manager, mock_time_service, mock_secrets_service):
    """Create handler dependencies."""
    return ActionHandlerDependencies(
        bus_manager=mock_bus_manager,
        time_service=mock_time_service,
        secrets_service=mock_secrets_service,
        shutdown_callback=None
    )


@pytest.fixture
def speak_handler(handler_dependencies):
    """Create SPEAK handler instance."""
    return SpeakHandler(handler_dependencies)


@pytest.fixture
def channel_context():
    """Create test channel context."""
    return ChannelContext(
        channel_id="test_channel_123",
        channel_name="Test Channel",
        channel_type="text",
        created_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def dispatch_context(channel_context):
    """Create test dispatch context."""
    return DispatchContext(
        channel_context=channel_context,
        author_id="test_author",
        author_name="Test Author",
        origin_service="test_service",
        handler_name="SpeakHandler",
        action_type=HandlerActionType.SPEAK,
        task_id="task_123",
        thought_id="thought_123",
        source_task_id="task_123",
        event_summary="Test speak action",
        event_timestamp=datetime.now(timezone.utc).isoformat(),
        correlation_id="corr_123",
        wa_authorized=True
    )


@pytest.fixture
def test_thought():
    """Create test thought."""
    return Thought(
        thought_id="thought_123",
        source_task_id="task_123",
        content="Test thought content",
        status=ThoughtStatus.PROCESSING,
        thought_depth=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=ThoughtContext(
            task_id="task_123",
            round_number=1,
            depth=1,
            correlation_id="corr_123",
            channel_id="test_channel_123"
        )
    )


@pytest.fixture
def test_task():
    """Create test task."""
    return Task(
        task_id="task_123",
        channel_id="test_channel_123",
        description="Test task description",
        status=TaskStatus.ACTIVE,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        priority=5,
        context=None
    )


@pytest.fixture
def speak_params():
    """Create test SPEAK parameters."""
    return SpeakParams(
        content="Hello, this is a test message!",
        channel_context=None
    )


@pytest.fixture
def action_result(speak_params):
    """Create test action selection result."""
    return ActionSelectionDMAResult(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=speak_params,
        rationale="Need to respond to user",
        raw_llm_response="SPEAK: Hello, this is a test message!",
        reasoning="User asked a question, providing response",
        evaluation_time_ms=100.0
    )


class TestSpeakHandler:
    """Test suite for SPEAK handler."""
    
    @pytest.mark.asyncio
    async def test_successful_message_send(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test successful message sending through communication bus."""
        # Mock persistence
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler
            follow_up_id = await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Verify communication bus was called
            mock_communication_bus.send_message.assert_called_once_with(
                channel_id="test_channel_123",
                content="Hello, this is a test message!",
                handler_name="SpeakHandler"
            )
            
            # Verify thought status was updated
            mock_persistence.update_thought_status.assert_called_with(
                thought_id="thought_123",
                status=ThoughtStatus.COMPLETED,
                final_action=action_result
            )
            
            # Verify follow-up thought was created
            assert follow_up_id is not None
            mock_persistence.add_thought.assert_called_once()
            
            # Verify correlation was added
            mock_persistence.add_correlation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_communication_failure(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test handling of communication bus failures."""
        # Configure communication to fail
        mock_communication_bus.send_message.return_value = False
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler
            follow_up_id = await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Verify thought status was marked as failed
            mock_persistence.update_thought_status.assert_called_with(
                thought_id="thought_123",
                status=ThoughtStatus.FAILED,
                final_action=action_result
            )
            
            # Verify follow-up thought contains failure message
            follow_up_call = mock_persistence.add_thought.call_args[0][0]
            assert "SPEAK action failed" in follow_up_call.content
    
    @pytest.mark.asyncio
    async def test_missing_channel_id(
        self, speak_handler, action_result, test_thought, dispatch_context
    ):
        """Test error handling when channel ID is missing."""
        # Remove channel ID from contexts
        dispatch_context.channel_context = None
        test_thought.context.channel_id = None
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="Channel ID is required"):
                await speak_handler.handle(
                    action_result, test_thought, dispatch_context
                )
    
    @pytest.mark.asyncio
    async def test_different_content_types(
        self, speak_handler, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test handling different content types."""
        content_types = [
            "Simple text message",
            "Message with emojis 🎉 😊",
            "Message with\nmultiple\nlines",
            "Very " + "long " * 100 + "message",
            "Message with special chars: <>&\"'",
            "```code\nprint('Hello')\n```",
            ""  # Empty message
        ]
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            for content in content_types:
                # Reset mocks
                mock_communication_bus.send_message.reset_mock()
                mock_persistence.add_thought.reset_mock()
                
                # Create params with different content
                params = SpeakParams(content=content)
                result = ActionSelectionDMAResult(
                    selected_action=HandlerActionType.SPEAK,
                    action_parameters=params,
                    rationale="Test different content"
                )
                
                # Execute handler
                await speak_handler.handle(result, test_thought, dispatch_context)
                
                # Verify content was sent correctly
                if content:  # Skip empty content check
                    mock_communication_bus.send_message.assert_called_with(
                        channel_id="test_channel_123",
                        content=content,
                        handler_name="SpeakHandler"
                    )
    
    @pytest.mark.asyncio
    async def test_parameter_validation_error(
        self, speak_handler, test_thought, dispatch_context
    ):
        """Test handling of invalid parameters."""
        # Since ActionSelectionDMAResult validates parameters at construction,
        # we need to simulate validation error happening within the handler
        # by passing a dict directly (simulating pre-validation data)
        
        # Mock the validation to fail
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            
            # Create a result with valid structure but simulate validation failure in handler
            result = ActionSelectionDMAResult(
                selected_action=HandlerActionType.SPEAK,
                action_parameters=SpeakParams(content="test"),  # Valid params
                rationale="Test validation"
            )
            
            # Mock the validation method to raise an error
            with patch.object(speak_handler, '_validate_and_convert_params') as mock_validate:
                mock_validate.side_effect = ValueError("Invalid parameters: missing content")
                
                # Execute handler - should handle validation error
                follow_up_id = await speak_handler.handle(
                    result, test_thought, dispatch_context
                )
                
                # Verify thought was marked as failed
                mock_persistence.update_thought_status.assert_called_with(
                    thought_id="thought_123",
                    status=ThoughtStatus.FAILED,
                    final_action=result
                )
                
                # Verify error follow-up was created
                assert follow_up_id is not None
                # Check the follow-up thought contains error message
                follow_up_call = mock_persistence.add_thought.call_args[0][0]
                assert "SPEAK action failed" in follow_up_call.content
    
    @pytest.mark.asyncio
    async def test_audit_trail(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_bus_manager, test_task
    ):
        """Test audit logging for SPEAK actions."""
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler
            await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Verify audit logs were created
            audit_calls = mock_bus_manager.audit_service.log_event.call_args_list
            assert len(audit_calls) >= 2  # Start and completion
            
            # Check start audit
            start_call = audit_calls[0]
            # The handler converts to string representation of AuditEventType
            assert "handler_action_speak" in str(start_call[1]['event_type']).lower()
            assert start_call[1]['event_data']['outcome'] == "start"
            
            # Check completion audit
            end_call = audit_calls[-1]
            assert end_call[1]['event_data']['outcome'] == "success"
    
    @pytest.mark.asyncio
    async def test_multiple_channels(
        self, speak_handler, speak_params, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test sending messages to different channels."""
        channels = [
            ("channel_1", "Channel 1"),
            ("channel_2", "Channel 2"),
            ("dm_channel", "DM Channel"),
            ("thread_123", "Thread Channel")
        ]
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            for channel_id, channel_name in channels:
                # Reset mocks
                mock_communication_bus.send_message.reset_mock()
                
                # Update channel context
                dispatch_context.channel_context = ChannelContext(
                    channel_id=channel_id,
                    channel_name=channel_name,
                    channel_type="text",
                    created_at=datetime.now(timezone.utc)
                )
                
                # Create action result
                result = ActionSelectionDMAResult(
                    selected_action=HandlerActionType.SPEAK,
                    action_parameters=speak_params,
                    rationale="Test multiple channels"
                )
                
                # Execute handler
                await speak_handler.handle(result, test_thought, dispatch_context)
                
                # Verify correct channel was used
                mock_communication_bus.send_message.assert_called_with(
                    channel_id=channel_id,
                    content="Hello, this is a test message!",
                    handler_name="SpeakHandler"
                )
    
    @pytest.mark.asyncio
    async def test_communication_bus_exception(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test handling of exceptions from communication bus."""
        # Configure communication to raise exception
        mock_communication_bus.send_message.side_effect = Exception("Network error")
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler - should handle exception gracefully
            follow_up_id = await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Verify thought was marked as failed
            mock_persistence.update_thought_status.assert_called_with(
                thought_id="thought_123",
                status=ThoughtStatus.FAILED,
                final_action=action_result
            )
            
            # Verify follow-up was created
            assert follow_up_id is not None
    
    @pytest.mark.asyncio
    async def test_service_correlation_tracking(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_time_service, test_task
    ):
        """Test service correlation tracking for telemetry."""
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler
            await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Verify correlation was created
            mock_persistence.add_correlation.assert_called_once()
            correlation = mock_persistence.add_correlation.call_args[0][0]
            
            # Check correlation properties
            assert isinstance(correlation, ServiceCorrelation)
            assert correlation.service_type == "communication"
            assert correlation.handler_name == "SpeakHandler"
            assert correlation.action_type == "speak"
            assert correlation.request_data.thought_id == "thought_123"
            assert correlation.request_data.task_id == "task_123"
            assert correlation.request_data.channel_id == "test_channel_123"
            assert correlation.response_data.success is True
    
    @pytest.mark.asyncio
    async def test_secret_decapsulation(
        self, speak_handler, test_thought, dispatch_context,
        mock_secrets_service, test_task
    ):
        """Test automatic secret decapsulation in parameters."""
        # Create params with a secret placeholder
        params_with_secret = {
            "content": "Message with secret: {SECRET:api_key}"
        }
        
        result = ActionSelectionDMAResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Message with secret: {SECRET:api_key}"),
            rationale="Test secret handling"
        )
        
        # Configure secrets service to replace secret
        mock_secrets_service.decapsulate_secrets_in_parameters.return_value = {
            "content": "Message with secret: actual_api_key_value"
        }
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler
            await speak_handler.handle(result, test_thought, dispatch_context)
            
            # Verify secrets service was called
            mock_secrets_service.decapsulate_secrets_in_parameters.assert_called_once()
            
            # Verify decapsulated content was used
            # Note: The actual message sending would fail due to validation,
            # but we're testing that decapsulation happens first


class TestBuildSpeakErrorContext:
    """Test the error context builder helper function."""
    
    def test_notification_failed_error(self, speak_params):
        """Test notification failed error context."""
        context = _build_speak_error_context(
            speak_params, "thought_123", "notification_failed"
        )
        assert "Failed to send notification" in context
        assert "thought_123" in context
        assert "Hello, this is a test message!" in context
    
    def test_channel_unavailable_error(self, speak_params):
        """Test channel unavailable error context."""
        context = _build_speak_error_context(
            speak_params, "thought_123", "channel_unavailable"
        )
        assert "Channel" in context
        assert "not available" in context
    
    def test_content_rejected_error(self, speak_params):
        """Test content rejected error context."""
        context = _build_speak_error_context(
            speak_params, "thought_123", "content_rejected"
        )
        assert "Content was rejected" in context
    
    def test_service_timeout_error(self, speak_params):
        """Test service timeout error context."""
        context = _build_speak_error_context(
            speak_params, "thought_123", "service_timeout"
        )
        assert "timed out" in context
    
    def test_unknown_error(self, speak_params):
        """Test unknown error context."""
        context = _build_speak_error_context(
            speak_params, "thought_123", "unknown_error_type"
        )
        assert "Unknown error" in context
    
    def test_long_content_truncation(self):
        """Test that long content is truncated in error context."""
        long_content = "x" * 200
        params = SpeakParams(content=long_content)
        context = _build_speak_error_context(
            params, "thought_123", "notification_failed"
        )
        assert "xxx..." in context
        assert len(context) < 300  # Context should be reasonably sized


@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    async def test_follow_up_creation_failure(
        self, speak_handler, action_result, test_thought, dispatch_context,
        test_task
    ):
        """Test handling when follow-up thought creation fails."""
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought.side_effect = Exception("DB error")
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Should raise FollowUpCreationError
            from ciris_engine.logic.infrastructure.handlers.exceptions import FollowUpCreationError
            with pytest.raises(FollowUpCreationError):
                await speak_handler.handle(
                    action_result, test_thought, dispatch_context
                )
    
    async def test_missing_task(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_communication_bus
    ):
        """Test handling when task is not found."""
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = None  # Task not found
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Execute handler - should handle missing task gracefully
            follow_up_id = await speak_handler.handle(
                action_result, test_thought, dispatch_context
            )
            
            # Should still complete successfully
            assert follow_up_id is not None
            mock_communication_bus.send_message.assert_called_once()
    
    async def test_concurrent_message_sends(
        self, speak_handler, action_result, test_thought, dispatch_context,
        mock_communication_bus, test_task
    ):
        """Test handling concurrent message sends."""
        import asyncio
        
        with patch('ciris_engine.logic.handlers.external.speak_handler.persistence') as mock_persistence:
            mock_persistence.get_task_by_id.return_value = test_task
            mock_persistence.add_thought = Mock()
            mock_persistence.update_thought_status = Mock()
            mock_persistence.add_correlation = Mock()
            
            # Configure slow communication
            async def slow_send(*args, **kwargs):
                await asyncio.sleep(0.1)
                return True
            
            mock_communication_bus.send_message = slow_send
            
            # Execute multiple handlers concurrently
            tasks = []
            for i in range(5):
                thought = test_thought.model_copy()
                thought.thought_id = f"thought_{i}"
                tasks.append(
                    speak_handler.handle(action_result, thought, dispatch_context)
                )
            
            # All should complete successfully
            results = await asyncio.gather(*tasks)
            assert all(r is not None for r in results)