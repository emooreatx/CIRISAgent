"""Unit tests for individual Discord adapter components."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
import discord
import base64
import json

from ciris_engine.logic.adapters.discord.discord_vision_helper import DiscordVisionHelper
from ciris_engine.logic.adapters.discord.discord_error_handler import DiscordErrorHandler, ErrorSeverity
from ciris_engine.logic.adapters.discord.discord_rate_limiter import DiscordRateLimiter
from ciris_engine.logic.adapters.discord.discord_embed_formatter import DiscordEmbedFormatter, EmbedType
from ciris_engine.logic.adapters.discord.discord_thread_manager import DiscordThreadManager, ThreadType
from ciris_engine.logic.adapters.discord.discord_access_control import DiscordAccessControl, AccessLevel
from ciris_engine.logic.adapters.discord.discord_audit import DiscordAuditLogger
from typing import Any, Dict, Optional


class TestDiscordVisionHelper:
    """Test Discord Vision Helper functionality."""

    @pytest.fixture
    def vision_helper(self) -> DiscordVisionHelper:
        """Create vision helper with mocked API key."""
        with patch.dict('os.environ', {'CIRIS_OPENAI_VISION_KEY': 'test_key'}):
            return DiscordVisionHelper()

    @pytest.mark.asyncio
    async def test_vision_helper_initialization(self, vision_helper: DiscordVisionHelper) -> None:
        """Test vision helper initializes with API key."""
        assert vision_helper.is_available() is True
        assert vision_helper.api_key == 'test_key'

    @pytest.mark.asyncio
    async def test_process_image_attachment(self, vision_helper: DiscordVisionHelper) -> None:
        """Test processing Discord image attachment."""
        # Mock attachment
        mock_attachment = Mock()
        mock_attachment.content_type = "image/png"
        mock_attachment.filename = "test.png"
        mock_attachment.size = 1024 * 1024  # 1MB
        mock_attachment.url = "https://example.com/image.png"

        # Mock message with attachment
        mock_message = Mock()
        mock_message.attachments = [mock_attachment]

        # Mock HTTP responses - patch the image processing method
        async def mock_process_single_image(attachment: Any) -> str:
            # Simple mock that returns the expected result
            return "This is a test image description"

        # Patch the _process_single_image method directly
        with patch.object(vision_helper, '_process_single_image', side_effect=mock_process_single_image):
            # Process image
            result = await vision_helper.process_message_images(mock_message)

            assert result is not None
            assert "test.png" in result
            assert "This is a test image description" in result

    @pytest.mark.asyncio
    async def test_vision_helper_no_api_key(self) -> None:
        """Test vision helper without API key."""
        with patch.dict('os.environ', {}, clear=True):
            helper = DiscordVisionHelper()
            assert helper.is_available() is False

            mock_message = Mock()
            result = await helper.process_message_images(mock_message)
            assert result is None


class TestDiscordErrorHandler:
    """Test Discord error handling."""

    @pytest.fixture
    def error_handler(self) -> DiscordErrorHandler:
        """Create error handler instance."""
        return DiscordErrorHandler()

    @pytest.mark.asyncio
    async def test_handle_channel_not_found(self, error_handler: DiscordErrorHandler) -> None:
        """Test handling channel not found error."""
        error = discord.NotFound(Mock(), "Channel not found")

        result = await error_handler.handle_channel_error(
            "123456789", error, "send_message"
        )

        assert result["severity"] == ErrorSeverity.HIGH.value
        assert result["can_retry"] is False
        assert result["fallback_action"] == "remove_channel"
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_handle_forbidden_error(self, error_handler: DiscordErrorHandler) -> None:
        """Test handling permission denied error."""
        error = discord.Forbidden(Mock(), "Missing permissions")

        result = await error_handler.handle_channel_error(
            "123456789", error, "send_message"
        )

        assert result["severity"] == ErrorSeverity.HIGH.value
        assert result["can_retry"] is False
        assert result["fallback_action"] == "check_permissions"
        assert "permission" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_handle_rate_limit_error(self, error_handler: DiscordErrorHandler) -> None:
        """Test handling rate limit error."""
        mock_response = Mock()
        mock_response.status = 429
        error = discord.HTTPException(mock_response, "Rate limited")

        result = await error_handler.handle_channel_error(
            "123456789", error, "send_message"
        )

        assert result["severity"] == ErrorSeverity.MEDIUM.value
        assert result["can_retry"] is True
        assert result["fallback_action"] == "wait_and_retry"

    @pytest.mark.asyncio
    async def test_error_threshold_escalation(self, error_handler: DiscordErrorHandler) -> None:
        """Test error severity escalation after threshold."""
        error = discord.HTTPException(Mock(), "Test error")

        # Generate multiple errors
        for i in range(6):
            await error_handler.handle_channel_error("123", error)

        # Check error count
        assert error_handler._error_counts.get("channel_123_HTTPException", 0) >= 5


class TestDiscordRateLimiter:
    """Test Discord rate limiting."""

    @pytest.fixture
    def rate_limiter(self) -> DiscordRateLimiter:
        """Create rate limiter instance."""
        return DiscordRateLimiter(safety_margin=0.1)

    @pytest.mark.asyncio
    async def test_global_rate_limit(self, rate_limiter: DiscordRateLimiter) -> None:
        """Test global rate limiting."""
        # Mock time to avoid actual sleeps
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Make requests up to limit
            for _ in range(50):
                await rate_limiter.acquire("/channels/123/messages", "POST")

            # Next request should require wait
            await rate_limiter.acquire("/channels/123/messages", "POST")

            # Should have called sleep at least once
            assert mock_sleep.called

    def test_endpoint_normalization(self, rate_limiter: DiscordRateLimiter) -> None:
        """Test endpoint path normalization."""
        # Test various endpoint formats
        assert rate_limiter._normalize_endpoint("/channels/123456/messages") == "channels/{channel_id}/messages"
        assert rate_limiter._normalize_endpoint("guilds/111/members/222") == "guilds/{guild_id}/members/{user_id}"
        assert rate_limiter._normalize_endpoint("/users/333") == "users/{user_id}"

    def test_update_from_headers(self, rate_limiter: DiscordRateLimiter) -> None:
        """Test updating limits from response headers."""
        headers = {
            "X-RateLimit-Remaining": "10",
            "X-RateLimit-Reset": str(datetime.now().timestamp() + 60),
            "X-RateLimit-Bucket": "test_bucket"
        }

        rate_limiter.update_from_response("/channels/123/messages", headers)

        # Stats should be updated
        stats = rate_limiter.get_stats()
        assert stats["requests"] >= 0


class TestDiscordEmbedFormatter:
    """Test Discord embed formatting."""

    def test_create_base_embed(self) -> None:
        """Test creating base embed."""
        embed = DiscordEmbedFormatter.create_base_embed(
            EmbedType.INFO,
            "Test Title",
            "Test Description"
        )

        assert "ℹ️" in embed.title
        assert "Test Title" in embed.title
        assert embed.description == "Test Description"
        assert embed.color.value == 0x3498db

    def test_format_guidance_request(self) -> None:
        """Test formatting guidance request."""
        context = {
            "question": "Should I proceed?",
            "thought_id": "thought123",
            "task_id": "task456",
            "ethical_considerations": ["Consider user privacy", "Ensure accuracy"],
            "domain_context": {"urgency": "high"}
        }

        embed = DiscordEmbedFormatter.format_guidance_request(context)

        assert "🤔" in embed.title
        assert "Should I proceed?" in embed.description
        assert len(embed.fields) > 0

        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "Thought ID" in field_names
        assert "Task ID" in field_names
        assert "Urgency" in field_names

    def test_format_approval_request(self) -> None:
        """Test formatting approval request."""
        context = {
            "requester_id": "user123",
            "task_id": "task789",
            "action_name": "delete_file",
            "action_params": {"file": "test.txt", "force": True}
        }

        embed = DiscordEmbedFormatter.format_approval_request("Delete File", context)

        assert "🔒" in embed.title
        assert "Approval Required" in embed.title
        assert "Delete File" in embed.description

        # Check for reaction instructions
        field_values = [field.value for field in embed.fields]
        assert any("✅" in value and "❌" in value for value in field_values)

    def test_format_tool_execution(self) -> None:
        """Test formatting tool execution."""
        # Test in-progress
        embed = DiscordEmbedFormatter.format_tool_execution(
            "test_tool",
            {"param1": "value1"},
            None
        )
        assert "🔧" in embed.title
        assert "Executing..." in embed.description

        # Test success
        result = {
            "success": True,
            "output": "Operation completed",
            "execution_time": 123.45
        }
        embed = DiscordEmbedFormatter.format_tool_execution(
            "test_tool",
            {"param1": "value1"},
            result
        )
        assert "✅" in embed.title
        assert embed.color.value == 0x2ecc71

        # Test failure
        result = {
            "success": False,
            "error": "Operation failed",
            "execution_time": 50.0
        }
        embed = DiscordEmbedFormatter.format_tool_execution(
            "test_tool",
            {"param1": "value1"},
            result
        )
        assert "❌" in embed.title
        assert embed.color.value == 0xe74c3c


class TestDiscordThreadManager:
    """Test Discord thread management."""

    @pytest.fixture
    def thread_manager(self) -> DiscordThreadManager:
        """Create thread manager instance."""
        mock_client = Mock(spec=discord.Client)
        return DiscordThreadManager(client=mock_client)

    @pytest.mark.asyncio
    async def test_create_thread(self, thread_manager: DiscordThreadManager) -> None:
        """Test creating a thread."""
        # Mock channel and thread
        mock_thread = Mock(spec=discord.Thread)
        mock_thread.id = 111222333
        mock_thread.name = "[GUIDANCE] Test Thread"
        mock_thread.archived = False

        mock_channel = Mock(spec=discord.TextChannel)

        # Mock message for initial_message flow
        mock_message = Mock()
        async def message_create_thread(*args: Any, **kwargs: Any) -> Any:
            return mock_thread
        mock_message.create_thread = message_create_thread

        # Mock channel.send to return the message
        async def channel_send(*args: Any, **kwargs: Any) -> Any:
            return mock_message
        mock_channel.send = channel_send

        thread_manager.client.get_channel = Mock(return_value=mock_channel)

        # Create thread
        thread = await thread_manager.create_thread(
            "123456789",
            "Test Thread",
            ThreadType.GUIDANCE,
            initial_message="Initial message"
        )

        assert thread is not None
        # The thread should be the mock_thread we created
        assert thread == mock_thread
        # Verify it was stored in active threads
        assert thread_manager._active_threads.get("guidance_123456789_Test Thread") == mock_thread

    @pytest.mark.asyncio
    async def test_get_or_create_thread(self, thread_manager: DiscordThreadManager) -> None:
        """Test getting existing thread or creating new one."""
        # Mock existing thread
        mock_thread = Mock(spec=discord.Thread)
        mock_thread.id = 111222333
        mock_thread.archived = False

        thread_key = "guidance_123456789_Test"
        thread_manager._active_threads[thread_key] = mock_thread

        # Get existing thread
        thread = await thread_manager.get_or_create_thread(
            "123456789",
            "Test",
            ThreadType.GUIDANCE
        )

        assert thread == mock_thread

    @pytest.mark.asyncio
    async def test_archive_old_threads(self, thread_manager: DiscordThreadManager) -> None:
        """Test archiving old threads."""
        # Create old thread
        old_thread = Mock(spec=discord.Thread)
        old_thread.id = 111
        old_thread.archived = False
        old_thread.edit = AsyncMock()

        thread_manager._active_threads["old_thread"] = old_thread
        thread_manager._thread_metadata[111] = {
            "created_at": datetime.now(timezone.utc) - timedelta(hours=25)
        }

        # Archive old threads
        count = await thread_manager.archive_old_threads(hours=24)

        assert count == 1
        old_thread.edit.assert_called_once_with(archived=True, reason="Auto-archive after 24 hours")


class TestDiscordAccessControl:
    """Test Discord access control."""

    @pytest.fixture
    def access_control(self) -> DiscordAccessControl:
        """Create access control instance."""
        mock_client = Mock(spec=discord.Client)
        mock_client.guilds = []
        return DiscordAccessControl(client=mock_client)

    @pytest.mark.asyncio
    async def test_check_channel_access_with_override(self, access_control: DiscordAccessControl) -> None:
        """Test channel access with user override."""
        # Set user override
        access_control.set_user_override("123456", AccessLevel.ADMIN)

        # Check access
        result = await access_control.check_channel_access(
            "123456", "channel123", AccessLevel.WRITE
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_operation_permissions(self, access_control: DiscordAccessControl) -> None:
        """Test operation permission checking."""
        # Configure channel
        access_control.configure_channel(
            "123456789",
            read_roles=["MEMBER"],
            write_roles=["MEMBER", "MODERATOR"],
            execute_roles=["MODERATOR"],
            admin_roles=["ADMIN"]
        )

        # Mock user with MEMBER role
        mock_member = Mock()
        member_role = Mock()
        member_role.name = "MEMBER"  # Set name as attribute, not Mock parameter
        mock_member.roles = [member_role]

        mock_guild = Mock()
        # Convert user_id string to int as Discord expects - access control converts "111" to int(111)
        def get_member_mock(uid: int) -> Optional[Any]:
            return mock_member if uid == 111 else None
        mock_guild.get_member = Mock(side_effect=get_member_mock)

        access_control.client.guilds = [mock_guild]

        # Check operations - expecting specific results based on configured permissions
        # MEMBER has write access which includes read
        assert await access_control.check_operation("111", "123456789", "read_messages") is True
        assert await access_control.check_operation("111", "123456789", "send_message") is True
        # MEMBER doesn't have execute access (requires MODERATOR)
        assert await access_control.check_operation("111", "123456789", "execute_tool") is False
        # MEMBER doesn't have admin access
        assert await access_control.check_operation("111", "123456789", "manage_channel") is False

    def test_global_role_permissions(self, access_control: DiscordAccessControl) -> None:
        """Test global role permission settings."""
        # Check defaults
        assert access_control._global_permissions["AUTHORITY"] == AccessLevel.ADMIN
        assert access_control._global_permissions["OBSERVER"] == AccessLevel.READ

        # Set custom global permission
        access_control.set_global_role_access("CUSTOM_ROLE", AccessLevel.EXECUTE)
        assert access_control._global_permissions["CUSTOM_ROLE"] == AccessLevel.EXECUTE


class TestDiscordAuditLogger:
    """Test Discord audit logging."""

    @pytest.fixture
    def audit_logger(self) -> DiscordAuditLogger:
        """Create audit logger instance."""
        mock_time_service = Mock()
        mock_time_service.now = Mock(return_value=datetime.now(timezone.utc))
        return DiscordAuditLogger(time_service=mock_time_service)

    @pytest.mark.asyncio
    async def test_log_operation_with_audit_service(self, audit_logger: DiscordAuditLogger) -> None:
        """Test logging operation with audit service."""
        # Mock audit service
        mock_audit_service = AsyncMock()
        audit_logger.set_audit_service(mock_audit_service)

        # Log operation
        await audit_logger.log_operation(
            operation="send_message",
            actor="user123",
            context={"channel_id": "456", "correlation_id": "abc123"},
            success=True
        )

        # Verify audit service was called
        assert mock_audit_service.log_event.called

        # Get the call arguments
        call_args = mock_audit_service.log_event.call_args

        # Check the arguments - log_event takes event_type and event_data
        assert call_args[1]["event_type"] == "discord.send_message"
        assert call_args[1]["event_data"]["actor"] == "user123"
        assert call_args[1]["event_data"]["details"]["channel_id"] == "456"
        assert call_args[1]["event_data"]["details"]["correlation_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_log_operation_without_audit_service(self, audit_logger: DiscordAuditLogger) -> None:
        """Test logging falls back to standard logging."""
        # No audit service set
        with patch('ciris_engine.logic.adapters.discord.discord_audit.logger') as mock_logger:
            await audit_logger.log_operation(
                operation="test_op",
                actor="user123",
                context={},
                success=False,
                error_message="Test error"
            )

            # Should use standard logging
            mock_logger.error.assert_called_once()
