"""
Tests for Discord adapter deferral handling.

Tests how the Discord adapter handles deferrals, including
notifications to human WAs and deferral resolution through Discord.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock

import pytest

from ciris_engine.schemas.services.authority.wise_authority import PendingDeferral
from ciris_engine.schemas.services.authority_core import DeferralResponse, WACertificate, WARole


class MockDiscordMessage:
    """Mock Discord message for testing."""

    def __init__(self, content: str, author_id: str = "123456", channel_id: str = "789012"):
        self.content = content
        self.author = Mock(id=author_id, name=f"User_{author_id}", mention=f"<@{author_id}>")
        self.channel = Mock(id=channel_id, name=f"channel_{channel_id}", send=AsyncMock())
        self.guild = Mock(id="111111", name="Test Guild")
        self.created_at = datetime.now(timezone.utc)
        self.id = "msg_" + str(hash(content))[:8]


class MockDiscordAdapter:
    """Mock Discord adapter with deferral handling."""

    def __init__(self, wa_service=None):
        self.wa_service = wa_service or Mock()
        self.sent_messages: List[Dict[str, Any]] = []
        self.deferral_notifications: Dict[str, List[str]] = {}  # channel_id -> messages

    async def send_deferral_notification(
        self, channel_id: str, deferral: PendingDeferral, wa_mentions: List[str]
    ) -> None:
        """Send deferral notification to Discord channel."""
        # Build notification message
        mention_str = " ".join(wa_mentions) if wa_mentions else "@here"

        message = f"""
🚨 **Deferral Requiring Review** 🚨
{mention_str}

**Deferral ID**: `{deferral.deferral_id}`
**Priority**: {deferral.priority.upper()}
**Reason**: {deferral.reason}
**Task**: {deferral.task_id}
**Created**: {deferral.created_at.strftime("%Y-%m-%d %H:%M UTC")}

**Required Role**: {deferral.requires_role or "Any WA"}

To resolve, use: `/wa resolve {deferral.deferral_id} [approve|reject|modify] [reason]`
"""

        # Store notification
        if channel_id not in self.deferral_notifications:
            self.deferral_notifications[channel_id] = []
        self.deferral_notifications[channel_id].append(message)

        # Track sent message
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "content": message,
                "type": "deferral_notification",
                "deferral_id": deferral.deferral_id,
                "mentions": wa_mentions,
            }
        )

    async def handle_wa_command(self, message: MockDiscordMessage) -> Optional[str]:
        """Handle WA commands from Discord."""
        parts = message.content.strip().split()

        if len(parts) < 2 or parts[0] != "/wa":
            return None

        command = parts[1]

        if command == "list":
            # List pending deferrals
            deferrals = await self.wa_service.get_pending_deferrals()
            if not deferrals:
                return "No pending deferrals."

            response = "**Pending Deferrals:**\n"
            for d in deferrals:
                response += f"• `{d.deferral_id}` - {d.reason[:50]}... (Priority: {d.priority})\n"

            return response

        elif command == "resolve" and len(parts) >= 4:
            deferral_id = parts[2]
            resolution = parts[3]
            reason = " ".join(parts[4:]) if len(parts) > 4 else "No reason provided"

            # Check if user is authorized WA
            wa_cert = await self._get_wa_cert(message.author.id)
            if not wa_cert or wa_cert.role != WARole.AUTHORITY:
                return "❌ You must be an AUTHORITY to resolve deferrals."

            # Create resolution
            if resolution not in ["approve", "reject", "modify"]:
                return "❌ Resolution must be: approve, reject, or modify"

            response = DeferralResponse(
                approved=(resolution == "approve"),
                reason=reason,
                modified_time=None,
                wa_id=wa_cert.wa_id,
                signature=f"discord_{message.id}",
            )

            # Resolve deferral
            try:
                result = await self.wa_service.resolve_deferral(deferral_id, response)
                if result:
                    action_past = {"approve": "approved", "reject": "rejected", "modify": "modified"}[resolution]
                    return f"✅ Deferral `{deferral_id}` {action_past} successfully."
                else:
                    return f"❌ Failed to resolve deferral `{deferral_id}`."
            except Exception as e:
                return f"❌ Error resolving deferral: {str(e)}"

        return "❌ Unknown command. Use: `/wa list` or `/wa resolve <id> <approve|reject|modify> <reason>`"

    async def _get_wa_cert(self, discord_user_id: str) -> Optional[WACertificate]:
        """Get WA certificate for Discord user."""
        # Mock implementation - in real system would check actual certs
        if discord_user_id == "wa_authority_discord":
            # Create valid WA ID matching pattern: wa-YYYY-MM-DD-XXXXXX
            wa_id = f"wa-2024-01-01-TEST{discord_user_id[:2].upper()}"
            return WACertificate(
                wa_id=wa_id,
                name="Discord Authority",
                role=WARole.AUTHORITY,
                pubkey="dGVzdF9wdWJrZXlfYmFzZTY0dXJs",  # Base64url encoded
                jwt_kid="test-jwt-kid",
                scopes_json='["resolve_deferrals", "admin"]',  # JSON array string
                created_at=datetime.now(timezone.utc),
                password_hash=None,
                api_key_hash=None,
                oauth_provider=None,
                oauth_external_id=None,
                auto_minted=False,
                veilid_id=None,
                parent_wa_id=None,
                parent_signature=None,
                adapter_id="discord",
                adapter_name="Discord",
                adapter_metadata_json=None,
                last_auth=datetime.now(timezone.utc),
            )
        return None


class TestDiscordDeferrals:
    """Test Discord adapter deferral functionality."""

    @pytest.fixture
    def mock_wa_service(self):
        """Mock WA service for testing."""
        service = AsyncMock()

        # Setup pending deferrals
        service.get_pending_deferrals = AsyncMock(
            return_value=[
                PendingDeferral(
                    deferral_id="defer_001",
                    created_at=datetime.now(timezone.utc),
                    deferred_by="agent_123",
                    task_id="task_spam_001",
                    thought_id="thought_spam_001",
                    reason="Potential spam detected, needs human review",
                    channel_id="discord_123",
                    user_id="user_456",
                    priority="high",
                    requires_role="AUTHORITY",
                    status="pending",
                ),
                PendingDeferral(
                    deferral_id="defer_002",
                    created_at=datetime.now(timezone.utc) - timedelta(hours=1),
                    deferred_by="agent_123",
                    task_id="task_mod_001",
                    thought_id="thought_mod_001",
                    reason="User reported for inappropriate behavior",
                    channel_id="discord_456",
                    user_id="user_789",
                    priority="critical",
                    requires_role="AUTHORITY",
                    status="pending",
                ),
            ]
        )

        service.resolve_deferral = AsyncMock(return_value=True)

        return service

    @pytest.fixture
    def discord_adapter(self, mock_wa_service):
        """Create mock Discord adapter."""
        return MockDiscordAdapter(mock_wa_service)

    @pytest.mark.asyncio
    async def test_deferral_notification_sent(self, discord_adapter):
        """Test that deferral notifications are sent to Discord."""
        # Create a critical deferral
        deferral = PendingDeferral(
            deferral_id="defer_critical_001",
            created_at=datetime.now(timezone.utc),
            deferred_by="agent_123",
            task_id="task_security_001",
            thought_id="thought_security_001",
            reason="CRITICAL: Potential security threat detected in user message",
            channel_id="security_channel",
            user_id="suspect_user",
            priority="critical",
            requires_role="AUTHORITY",
            status="pending",
        )

        # Send notification with specific WA mentions
        wa_mentions = ["<@wa_security_lead>", "<@wa_moderator_001>"]
        await discord_adapter.send_deferral_notification("security_channel", deferral, wa_mentions)

        # Verify notification was sent
        assert len(discord_adapter.sent_messages) == 1
        sent = discord_adapter.sent_messages[0]

        assert sent["type"] == "deferral_notification"
        assert sent["deferral_id"] == "defer_critical_001"
        assert sent["channel_id"] == "security_channel"
        assert "<@wa_security_lead>" in sent["content"]
        assert "CRITICAL" in sent["content"]
        assert "Potential security threat" in sent["content"]

    @pytest.mark.asyncio
    async def test_list_deferrals_command(self, discord_adapter, mock_wa_service):
        """Test /wa list command to show pending deferrals."""
        # Create message from authorized user
        message = MockDiscordMessage("/wa list", author_id="wa_user")

        # Handle command
        response = await discord_adapter.handle_wa_command(message)

        # Verify response
        assert response is not None
        assert "Pending Deferrals:" in response
        assert "defer_001" in response
        assert "defer_002" in response
        assert "Priority: high" in response
        assert "Priority: critical" in response

    @pytest.mark.asyncio
    async def test_resolve_deferral_approve(self, discord_adapter, mock_wa_service):
        """Test approving a deferral through Discord."""
        # Create message from authorized WA
        message = MockDiscordMessage(
            "/wa resolve defer_001 approve Reviewed and confirmed not spam", author_id="wa_authority_discord"
        )

        # Handle command
        response = await discord_adapter.handle_wa_command(message)

        # Verify resolution
        assert "✅" in response
        assert "defer_001" in response
        assert "approved successfully" in response

        # Verify WA service was called
        mock_wa_service.resolve_deferral.assert_called_once()
        call_args = mock_wa_service.resolve_deferral.call_args
        assert call_args[0][0] == "defer_001"

        resolution = call_args[0][1]
        assert resolution.approved is True
        assert resolution.reason == "Reviewed and confirmed not spam"

    @pytest.mark.asyncio
    async def test_resolve_deferral_reject(self, discord_adapter, mock_wa_service):
        """Test rejecting a deferral through Discord."""
        # Create message from authorized WA
        message = MockDiscordMessage(
            "/wa resolve defer_002 reject User violated community guidelines", author_id="wa_authority_discord"
        )

        # Handle command
        response = await discord_adapter.handle_wa_command(message)

        # Verify resolution
        assert "✅" in response
        assert "defer_002" in response
        assert "rejected successfully" in response

        # Verify rejection
        call_args = mock_wa_service.resolve_deferral.call_args
        resolution = call_args[0][1]
        assert resolution.approved is False
        assert "violated community guidelines" in resolution.reason

    @pytest.mark.asyncio
    async def test_unauthorized_resolution_attempt(self, discord_adapter):
        """Test that non-AUTHORITY users cannot resolve deferrals."""
        # Create message from regular user
        message = MockDiscordMessage("/wa resolve defer_001 approve Should not work", author_id="regular_user_123")

        # Handle command
        response = await discord_adapter.handle_wa_command(message)

        # Should be rejected
        assert "❌" in response
        assert "must be an AUTHORITY" in response

    @pytest.mark.asyncio
    async def test_batch_deferral_notifications(self, discord_adapter):
        """Test sending multiple deferral notifications."""
        # Create multiple deferrals
        deferrals = [
            PendingDeferral(
                deferral_id=f"defer_batch_{i}",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=i * 10),
                deferred_by="agent_123",
                task_id=f"task_batch_{i}",
                thought_id=f"thought_batch_{i}",
                reason=f"Batch deferral {i} for testing",
                channel_id="batch_channel",
                user_id=f"user_{i}",
                priority=["low", "medium", "high", "critical"][i % 4],
                requires_role="AUTHORITY",
                status="pending",
            )
            for i in range(5)
        ]

        # Send all notifications
        for deferral in deferrals:
            await discord_adapter.send_deferral_notification("batch_channel", deferral, ["@here"])

        # Verify all sent
        assert len(discord_adapter.sent_messages) == 5
        assert all(msg["type"] == "deferral_notification" for msg in discord_adapter.sent_messages)

        # Verify channel grouping
        assert len(discord_adapter.deferral_notifications["batch_channel"]) == 5

    @pytest.mark.asyncio
    async def test_deferral_with_context_display(self, discord_adapter):
        """Test that deferral context is properly displayed."""
        # Create deferral with rich context
        deferral = PendingDeferral(
            deferral_id="defer_context_001",
            created_at=datetime.now(timezone.utc),
            deferred_by="agent_123",
            task_id="task_medical_001",
            thought_id="thought_medical_001",
            reason="Medical advice requested - requires licensed physician review",
            channel_id="medical_channel",
            user_id="patient_001",
            priority="high",
            requires_role="MEDICAL_AUTHORITY",
            status="pending",
            # Additional context could be in a separate field in real implementation
        )

        # Send notification
        await discord_adapter.send_deferral_notification("medical_channel", deferral, ["<@medical_wa_team>"])

        # Verify context is included
        sent = discord_adapter.sent_messages[0]
        assert "Medical advice requested" in sent["content"]
        assert "MEDICAL_AUTHORITY" in sent["content"]
        assert "**Priority**: HIGH" in sent["content"]

    @pytest.mark.asyncio
    async def test_invalid_wa_command(self, discord_adapter):
        """Test handling of invalid WA commands."""
        # Test various invalid commands
        invalid_commands = [
            "/wa",  # No subcommand
            "/wa unknown",  # Unknown subcommand
            "/wa resolve",  # Missing parameters
            "/wa resolve defer_001",  # Missing resolution
            "/wa resolve defer_001 maybe",  # Invalid resolution
        ]

        for cmd in invalid_commands:
            message = MockDiscordMessage(cmd)
            response = await discord_adapter.handle_wa_command(message)

            # Should return error or help
            assert response is None or "❌" in response or "Unknown command" in response

    @pytest.mark.asyncio
    async def test_deferral_resolution_with_modification(self, discord_adapter, mock_wa_service):
        """Test modifying a deferral through Discord."""
        # This would be a more complex command in real implementation
        message = MockDiscordMessage(
            "/wa resolve defer_001 modify Approve with additional monitoring for 7 days",
            author_id="wa_authority_discord",
        )

        # Handle command
        response = await discord_adapter.handle_wa_command(message)

        # Should succeed
        assert "✅" in response
        assert "modified successfully" in response

        # In a real implementation, this would create a DeferralResolution
        # with modified_action and modified_parameters


class TestDiscordDeferralIntegration:
    """Integration tests for Discord deferral flow."""

    @pytest.mark.asyncio
    async def test_full_discord_deferral_flow(self):
        """Test complete flow from deferral creation to Discord resolution."""
        # This would be a full integration test with:
        # 1. Agent creates deferral
        # 2. Discord adapter sends notification
        # 3. Human WA sees notification in Discord
        # 4. Human WA uses /wa commands to resolve
        # 5. Agent continues with WA guidance

        # Mock the full flow
        wa_service = AsyncMock()
        discord_adapter = MockDiscordAdapter(wa_service)

        # Step 1: Deferral created (simulated)
        deferral = PendingDeferral(
            deferral_id="integration_defer_001",
            created_at=datetime.now(timezone.utc),
            deferred_by="agent_123",
            task_id="task_integration_001",
            thought_id="thought_integration_001",
            reason="Complex decision requiring human judgment",
            channel_id="general_channel",
            user_id="user_asking",
            priority="medium",
            requires_role="AUTHORITY",
            status="pending",
        )

        # Step 2: Notification sent
        await discord_adapter.send_deferral_notification("general_channel", deferral, ["<@wa_on_duty>"])

        assert len(discord_adapter.sent_messages) == 1

        # Step 3: WA lists deferrals
        list_msg = MockDiscordMessage("/wa list", author_id="wa_authority_discord")
        wa_service.get_pending_deferrals.return_value = [deferral]

        list_response = await discord_adapter.handle_wa_command(list_msg)
        assert "integration_defer_001" in list_response

        # Step 4: WA resolves
        resolve_msg = MockDiscordMessage(
            "/wa resolve integration_defer_001 approve Proceed with standard protocol", author_id="wa_authority_discord"
        )

        resolution_response = await discord_adapter.handle_wa_command(resolve_msg)
        assert "✅" in resolution_response

        # Step 5: Verify resolution was processed
        wa_service.resolve_deferral.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
