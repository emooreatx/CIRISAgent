"""
Discord Tool Suite: Moderation, Channel Management, and Info Tools
Implements async tool handlers and registration for CIRIS ToolRegistry.
"""
import discord
from typing import Optional
from ciris_engine.schemas.services.tools_core import ToolResult, ToolExecutionStatus
from datetime import datetime

async def discord_delete_message(bot: discord.Client, channel_id: int, message_id: int) -> ToolResult:
    try:
        channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)
        if hasattr(channel, 'fetch_message'):
            msg = await channel.fetch_message(message_id)
            await msg.delete()
        else:
            raise ValueError(f"Channel {channel_id} does not support message fetching")
        return ToolResult(
            tool_name="discord_delete_message",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"message_id": str(message_id), "channel_id": str(channel_id)},
            error_message=None,
            execution_time_ms=None
        )
    except Exception as e:
        return ToolResult(
            tool_name="discord_delete_message",
            execution_status=ToolExecutionStatus.FAILED,
            result_data=None,
            error_message=str(e),
            execution_time_ms=None
        )

async def discord_timeout_user(bot: discord.Client, guild_id: int, user_id: int, duration_seconds: int, reason: Optional[str] = None) -> ToolResult:
    try:
        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
        from datetime import timedelta
        until = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
        await member.timeout(until, reason=reason)
        return ToolResult(
            tool_name="discord_timeout_user",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"user_id": str(user_id), "guild_id": str(guild_id), "until": until.isoformat()},
            error_message=None,
            execution_time_ms=None
        )
    except Exception as e:
        return ToolResult(
            tool_name="discord_timeout_user",
            execution_status=ToolExecutionStatus.FAILED,
            result_data=None,
            error_message=str(e),
            execution_time_ms=None
        )

async def discord_ban_user(bot: discord.Client, guild_id: int, user_id: int, reason: Optional[str] = None, delete_message_days: int = 0) -> ToolResult:
    try:
        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        user = await guild.fetch_member(user_id)
        await guild.ban(user, reason=reason, delete_message_days=delete_message_days)
        return ToolResult(
            tool_name="discord_ban_user",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"user_id": str(user_id), "guild_id": str(guild_id)},
            error_message=None,
            execution_time_ms=None
        )
    except Exception as e:
        return ToolResult(
            tool_name="discord_ban_user",
            execution_status=ToolExecutionStatus.FAILED,
            result_data=None,
            error_message=str(e),
            execution_time_ms=None
        )

async def discord_kick_user(bot: discord.Client, guild_id: int, user_id: int, reason: Optional[str] = None) -> ToolResult:
    try:
        guild = bot.get_guild(guild_id) or await bot.fetch_guild(guild_id)
        user = await guild.fetch_member(user_id)
        await guild.kick(user, reason=reason)
        return ToolResult(
            tool_name="discord_kick_user",
            execution_status=ToolExecutionStatus.SUCCESS,
            result_data={"user_id": str(user_id), "guild_id": str(guild_id)},
            error_message=None,
            execution_time_ms=None
        )
    except Exception as e:
        return ToolResult(
            tool_name="discord_kick_user",
            execution_status=ToolExecutionStatus.FAILED,
            result_data=None,
            error_message=str(e),
            execution_time_ms=None
        )

def register_discord_tools(registry: Any, bot: Any) -> None:
    """Register Discord tools in the ToolRegistry."""
    registry.register_tool(
        "discord_delete_message",
        schema={"channel_id": int, "message_id": int},
        handler=lambda args: discord_delete_message(bot, **args),
    )
    registry.register_tool(
        "discord_timeout_user",
        schema={"guild_id": int, "user_id": int, "duration_seconds": int, "reason": (str, type(None))},
        handler=lambda args: discord_timeout_user(bot, **args),
    )
    registry.register_tool(
        "discord_ban_user",
        schema={"guild_id": int, "user_id": int, "reason": (str, type(None)), "delete_message_days": int},
        handler=lambda args: discord_ban_user(bot, **args),
    )
    registry.register_tool(
        "discord_kick_user",
        schema={"guild_id": int, "user_id": int, "reason": (str, type(None))},
        handler=lambda args: discord_kick_user(bot, **args),
    )
