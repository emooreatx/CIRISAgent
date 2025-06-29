"""Discord embed formatting component for rich message presentation."""
import discord
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from enum import Enum

class EmbedType(Enum):
    """Types of embeds for different purposes."""
    INFO = ("ℹ️", 0x3498db)          # Blue
    SUCCESS = ("✅", 0x2ecc71)       # Green
    WARNING = ("⚠️", 0xf39c12)       # Orange
    ERROR = ("❌", 0xe74c3c)         # Red
    GUIDANCE = ("🤔", 0x9b59b6)      # Purple
    DEFERRAL = ("⏳", 0x95a5a6)      # Gray
    APPROVAL = ("🔒", 0xe67e22)      # Dark orange
    TOOL = ("🔧", 0x1abc9c)          # Turquoise
    AUDIT = ("📋", 0x34495e)         # Dark gray
    TASK = ("📝", 0x3498db)          # Blue


class DiscordEmbedFormatter:
    """Formats messages as rich Discord embeds."""

    @staticmethod
    def create_base_embed(embed_type: EmbedType, title: str,
                         description: Optional[str] = None) -> discord.Embed:
        """Create a base embed with consistent styling.

        Args:
            embed_type: Type of embed
            title: Embed title
            description: Optional description

        Returns:
            Discord embed object
        """
        icon, color = embed_type.value

        embed = discord.Embed(
            title=f"{icon} {title}",
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        return embed

    @classmethod
    def format_guidance_request(cls, context: Dict[str, Any]) -> discord.Embed:
        """Format a guidance request as an embed.

        Args:
            context: Guidance context

        Returns:
            Formatted embed
        """
        embed = cls.create_base_embed(
            EmbedType.GUIDANCE,
            "Guidance Request",
            context.get("question", "Guidance needed")
        )

        # Add context fields
        if context.get("thought_id"):
            embed.add_field(name="Thought ID", value=f"`{context['thought_id']}`", inline=True)

        if context.get("task_id"):
            embed.add_field(name="Task ID", value=f"`{context['task_id']}`", inline=True)

        if context.get("ethical_considerations"):
            considerations = "\n".join(f"• {c}" for c in context["ethical_considerations"][:5])
            embed.add_field(name="Ethical Considerations", value=considerations, inline=False)

        if context.get("domain_context"):
            domain = context["domain_context"]
            if domain.get("urgency"):
                embed.add_field(name="Urgency", value=domain["urgency"].upper(), inline=True)

        embed.set_footer(text="Please provide your guidance")
        return embed

    @classmethod
    def format_deferral_request(cls, deferral: Dict[str, Any]) -> discord.Embed:
        """Format a deferral request as an embed.

        Args:
            deferral: Deferral information

        Returns:
            Formatted embed
        """
        embed = cls.create_base_embed(
            EmbedType.DEFERRAL,
            "Decision Deferred",
            deferral.get("reason", "Decision requires additional consideration")
        )

        # Add deferral details
        embed.add_field(name="Deferral ID", value=f"`{deferral.get('deferral_id', 'N/A')}`", inline=True)
        embed.add_field(name="Task ID", value=f"`{deferral.get('task_id', 'N/A')}`", inline=True)
        embed.add_field(name="Thought ID", value=f"`{deferral.get('thought_id', 'N/A')}`", inline=True)

        if deferral.get("defer_until"):
            embed.add_field(name="Defer Until", value=f"<t:{int(deferral['defer_until'].timestamp())}:R>", inline=True)

        if deferral.get("context"):
            context_str = "\n".join(f"**{k}**: {v}" for k, v in list(deferral["context"].items())[:5])
            embed.add_field(name="Context", value=context_str[:1024], inline=False)

        return embed

    @classmethod
    def format_approval_request(cls, action: str, context: Dict[str, Any]) -> discord.Embed:
        """Format an approval request as an embed.

        Args:
            action: Action requiring approval
            context: Approval context

        Returns:
            Formatted embed
        """
        embed = cls.create_base_embed(
            EmbedType.APPROVAL,
            "Approval Required",
            f"Action: **{action}**"
        )

        # Add context
        embed.add_field(name="Requester", value=context.get("requester_id", "System"), inline=True)

        if context.get("task_id"):
            embed.add_field(name="Task", value=f"`{context['task_id']}`", inline=True)

        if context.get("thought_id"):
            embed.add_field(name="Thought", value=f"`{context['thought_id']}`", inline=True)

        if context.get("action_name"):
            embed.add_field(name="Action Type", value=context["action_name"], inline=True)

        if context.get("action_params"):
            params_str = "\n".join(f"• **{k}**: {v}" for k, v in list(context["action_params"].items())[:5])
            embed.add_field(name="Parameters", value=params_str[:1024], inline=False)

        embed.add_field(
            name="How to Respond",
            value="React with ✅ to approve or ❌ to deny",
            inline=False
        )

        return embed

    @classmethod
    def format_tool_execution(cls, tool_name: str, parameters: Dict[str, Any],
                            result: Optional[Dict[str, Any]] = None) -> discord.Embed:
        """Format tool execution information as an embed.

        Args:
            tool_name: Name of the tool
            parameters: Tool parameters
            result: Execution result (if available)

        Returns:
            Formatted embed
        """
        success = result and result.get("success", False) if result else None

        if success is None:
            embed_type = EmbedType.TOOL
            status = "Executing..."
        elif success:
            embed_type = EmbedType.SUCCESS
            status = "Completed"
        else:
            embed_type = EmbedType.ERROR
            status = "Failed"

        embed = cls.create_base_embed(
            embed_type,
            f"Tool: {tool_name}",
            status
        )

        # Add parameters
        if parameters:
            params_str = "\n".join(f"• **{k}**: `{v}`" for k, v in list(parameters.items())[:5])
            embed.add_field(name="Parameters", value=params_str[:1024], inline=False)

        # Add result if available
        if result:
            if result.get("output"):
                output = str(result["output"])[:1024]
                embed.add_field(name="Output", value=f"```\n{output}\n```", inline=False)

            if result.get("error"):
                embed.add_field(name="Error", value=result["error"][:1024], inline=False)

            if result.get("execution_time"):
                embed.add_field(name="Execution Time", value=f"{result['execution_time']:.2f}ms", inline=True)

        return embed

    @classmethod
    def format_task_status(cls, task: Dict[str, Any]) -> discord.Embed:
        """Format task status as an embed.

        Args:
            task: Task information

        Returns:
            Formatted embed
        """
        status = task.get("status", "unknown")
        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "failed": "❌",
            "deferred": "⏸️"
        }.get(status, "❓")

        embed = cls.create_base_embed(
            EmbedType.TASK,
            f"Task Status: {status_emoji} {status.replace('_', ' ').title()}",
            task.get("description", "Task in progress")
        )

        # Add task details
        embed.add_field(name="Task ID", value=f"`{task.get('id', 'N/A')}`", inline=True)
        embed.add_field(name="Priority", value=task.get("priority", "normal").upper(), inline=True)

        if task.get("progress"):
            embed.add_field(name="Progress", value=f"{task['progress']}%", inline=True)

        if task.get("created_at"):
            embed.add_field(name="Created", value=f"<t:{int(task['created_at'].timestamp())}:R>", inline=True)

        if task.get("subtasks"):
            subtask_str = "\n".join(
                f"{'✅' if st.get('completed') else '⬜'} {st.get('name', 'Subtask')}"
                for st in task["subtasks"][:5]
            )
            embed.add_field(name="Subtasks", value=subtask_str, inline=False)

        return embed

    @classmethod
    def format_audit_entry(cls, audit: Dict[str, Any]) -> discord.Embed:
        """Format an audit log entry as an embed.

        Args:
            audit: Audit information

        Returns:
            Formatted embed
        """
        embed = cls.create_base_embed(
            EmbedType.AUDIT,
            "Audit Log Entry",
            audit.get("action", "Unknown action")
        )

        # Add audit details
        embed.add_field(name="Actor", value=audit.get("actor", "System"), inline=True)
        embed.add_field(name="Service", value=audit.get("service", "Unknown"), inline=True)

        if audit.get("timestamp"):
            embed.add_field(name="Time", value=f"<t:{int(audit['timestamp'].timestamp())}:F>", inline=True)

        if audit.get("context"):
            context = audit["context"]
            if isinstance(context, dict):
                context_str = "\n".join(f"• **{k}**: {v}" for k, v in list(context.items())[:5])
                embed.add_field(name="Context", value=context_str[:1024], inline=False)

        if audit.get("success") is not None:
            embed.add_field(name="Result", value="✅ Success" if audit["success"] else "❌ Failed", inline=True)

        return embed

    @classmethod
    def format_error_message(cls, error_info: Dict[str, Any]) -> discord.Embed:
        """Format an error message as an embed.

        Args:
            error_info: Error information

        Returns:
            Formatted embed
        """
        severity = error_info.get("severity", "medium")
        embed_type = {
            "low": EmbedType.INFO,
            "medium": EmbedType.WARNING,
            "high": EmbedType.ERROR,
            "critical": EmbedType.ERROR
        }.get(severity, EmbedType.ERROR)

        embed = cls.create_base_embed(
            embed_type,
            f"Error: {error_info.get('error_type', 'Unknown')}",
            error_info.get("message", "An error occurred")
        )

        # Add error details
        if error_info.get("operation"):
            embed.add_field(name="Operation", value=error_info["operation"], inline=True)

        if error_info.get("severity"):
            embed.add_field(name="Severity", value=severity.upper(), inline=True)

        if error_info.get("can_retry") is not None:
            embed.add_field(name="Retryable", value="Yes" if error_info["can_retry"] else "No", inline=True)

        if error_info.get("suggested_fix"):
            embed.add_field(name="Suggested Fix", value=error_info["suggested_fix"], inline=False)

        return embed

    @classmethod
    def create_paginated_embed(cls, title: str, items: List[str],
                             page: int = 1, per_page: int = 10,
                             embed_type: EmbedType = EmbedType.INFO) -> discord.Embed:
        """Create a paginated embed for lists.

        Args:
            title: Embed title
            items: List of items to display
            page: Current page (1-indexed)
            per_page: Items per page
            embed_type: Type of embed

        Returns:
            Paginated embed
        """
        total_pages = (len(items) + per_page - 1) // per_page
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, len(items))

        page_items = items[start_idx:end_idx]

        embed = cls.create_base_embed(
            embed_type,
            title,
            "\n".join(page_items)
        )

        embed.set_footer(text=f"Page {page}/{total_pages} • Total items: {len(items)}")

        return embed
