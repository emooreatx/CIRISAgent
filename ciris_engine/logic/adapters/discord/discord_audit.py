"""Discord audit logging component."""

import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ciris_engine.protocols.services.graph.audit import AuditServiceProtocol
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)


class DiscordAuditLogger:
    """Handles audit logging for Discord operations."""

    def __init__(
        self,
        time_service: Optional["TimeServiceProtocol"] = None,
        audit_service: Optional["AuditServiceProtocol"] = None,
    ) -> None:
        """Initialize the audit logger.

        Args:
            time_service: Time service for consistent timestamps
            audit_service: Audit service for storing audit entries
        """
        self._time_service = time_service
        self._audit_service = audit_service

        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService

            self._time_service = TimeService()

    def set_audit_service(self, audit_service: "AuditServiceProtocol") -> None:
        """Set the audit service after initialization.

        Args:
            audit_service: Audit service instance
        """
        self._audit_service = audit_service

    async def log_operation(
        self,
        operation: str,
        actor: str,
        context: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Log a Discord operation to the audit trail.

        Args:
            operation: Operation name (e.g., "send_message", "fetch_guidance")
            actor: Who performed the operation (user ID or system component)
            context: Operation context and parameters
            success: Whether the operation succeeded
            error_message: Error message if operation failed
        """
        if not self._audit_service:
            # Fall back to standard logging
            if success:
                logger.info(f"Discord operation: {operation} by {actor} - {context}")
            else:
                logger.error(f"Discord operation failed: {operation} by {actor} - {error_message}")
            return

        try:
            # Create action description
            action = f"discord.{operation}"
            if not success:
                action = f"discord.{operation}.failed"

            # Create audit event data
            event_data = {
                "entity_id": context.get("channel_id", "unknown"),
                "actor": actor,
                "outcome": "success" if success else "failure",
                "severity": "info" if success else "error",
                "action": action,
                "resource": f"discord_channel_{context.get('channel_id', 'unknown')}",
                "reason": error_message if error_message else None,
                "details": {
                    "service_name": "discord_adapter",
                    "method_name": operation,
                    "channel_id": context.get("channel_id") or "",
                    "guild_id": context.get("guild_id") or "",
                    "correlation_id": context.get("correlation_id"),
                },
            }

            # Log to audit service
            await self._audit_service.log_event(event_type=action, event_data=event_data)

        except Exception as e:
            logger.error(f"Failed to log audit entry: {e}")

    async def log_message_sent(
        self, channel_id: str, author_id: str, message_content: str, correlation_id: Optional[str] = None
    ) -> None:
        """Log a message send operation.

        Args:
            channel_id: Discord channel ID
            author_id: Message author ID
            message_content: Content of the message (truncated)
            correlation_id: Optional correlation ID
        """
        # Truncate message for audit log
        truncated = message_content[:100] + "..." if len(message_content) > 100 else message_content

        await self.log_operation(
            operation="send_message",
            actor=author_id,
            context={
                "channel_id": channel_id,
                "message_preview": truncated,
                "message_length": len(message_content),
                "correlation_id": correlation_id,
            },
        )

    async def log_message_received(self, channel_id: str, author_id: str, author_name: str, message_id: str) -> None:
        """Log a message receive operation.

        Args:
            channel_id: Discord channel ID
            author_id: Message author ID
            author_name: Message author name
            message_id: Discord message ID
        """
        await self.log_operation(
            operation="receive_message",
            actor=author_id,
            context={"channel_id": channel_id, "author_name": author_name, "message_id": message_id},
        )

    async def log_guidance_request(
        self, channel_id: str, requester_id: str, context: Dict[str, Any], guidance_received: Optional[str] = None
    ) -> None:
        """Log a guidance request operation.

        Args:
            channel_id: Discord channel ID
            requester_id: Who requested guidance
            context: Guidance context
            guidance_received: The guidance that was received
        """
        await self.log_operation(
            operation="request_guidance",
            actor=requester_id,
            context={
                "channel_id": channel_id,
                "task_id": context.get("task_id"),
                "thought_id": context.get("thought_id"),
                "guidance_received": guidance_received is not None,
            },
        )

    async def log_approval_request(
        self, channel_id: str, requester_id: str, action: str, approval_status: str, approver_id: Optional[str] = None
    ) -> None:
        """Log an approval request operation.

        Args:
            channel_id: Discord channel ID
            requester_id: Who requested approval
            action: Action requiring approval
            approval_status: Status of the approval (pending, approved, denied, timeout)
            approver_id: Who approved/denied (if applicable)
        """
        await self.log_operation(
            operation="request_approval",
            actor=requester_id,
            context={
                "channel_id": channel_id,
                "action": action,
                "approval_status": approval_status,
                "approver_id": approver_id,
            },
        )

    async def log_permission_change(
        self, admin_id: str, target_id: str, permission: str, action: str, guild_id: str
    ) -> None:
        """Log a permission change operation.

        Args:
            admin_id: Who made the change
            target_id: User whose permissions changed
            permission: Permission name (AUTHORITY, OBSERVER)
            action: grant or revoke
            guild_id: Discord guild ID
        """
        await self.log_operation(
            operation=f"{action}_permission",
            actor=admin_id,
            context={"target_user_id": target_id, "permission": permission, "guild_id": guild_id},
        )

    async def log_tool_execution(
        self,
        user_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        success: bool,
        execution_time_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a tool execution operation.

        Args:
            user_id: Who executed the tool
            tool_name: Name of the tool
            parameters: Tool parameters
            success: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds
            error: Error message if failed
        """
        await self.log_operation(
            operation="execute_tool",
            actor=user_id,
            context={
                "tool_name": tool_name,
                "parameters": json.dumps(parameters) if parameters else "{}",
                "execution_time_ms": execution_time_ms,
            },
            success=success,
            error_message=error,
        )

    async def log_connection_event(
        self, event_type: str, guild_count: int, user_count: int, error: Optional[str] = None
    ) -> None:
        """Log a Discord connection event.

        Args:
            event_type: Type of event (connected, disconnected, reconnect)
            guild_count: Number of guilds
            user_count: Number of users
            error: Error message if applicable
        """
        await self.log_operation(
            operation=f"connection_{event_type}",
            actor="discord_adapter",
            context={"guild_count": guild_count, "user_count": user_count},
            success=error is None,
            error_message=error,
        )
