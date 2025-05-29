import logging
import os
import asyncio
import json # Added import for json.dumps
import re # Added import for regex
import ast # Added import for literal_eval
import uuid # Added import for uuid
from datetime import datetime, timezone # Added datetime imports
import discord # type: ignore
from typing import Dict, Any, Optional, List # Added List

from ciris_engine.utils import DEFAULT_WA

from pydantic import BaseModel, Field

from .base import Service
from ciris_engine.action_handlers.action_dispatcher import ActionDispatcher
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, ThoughtStatus
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import DeferParams, RejectParams, SpeakParams, ToolParams
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine import persistence  # For creating tasks and updating status
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.utils import extract_user_nick
from ciris_engine.services.tool_registry import ToolRegistry
from ciris_engine.adapters.discord.discord_tools import register_discord_tools
from ciris_engine.schemas.tool_schemas_v1 import ToolResult, ToolExecutionStatus

logger = logging.getLogger(__name__)

DISCORD_MESSAGE_LIMIT = 2000

class DiscordConfig(BaseModel):
    bot_token_env_var: str = Field(default="DISCORD_BOT_TOKEN", description="Environment variable for the Discord bot token.")
    deferral_channel_id_env_var: str = Field(default="DISCORD_DEFERRAL_CHANNEL_ID", description="Environment variable for the deferral channel ID.")
    wa_user_id_env_var: str = Field(default="DISCORD_WA_USER_ID", description="Environment variable for the Wise Authority user ID for corrections.")
    monitored_channel_id_env_var: str = Field(default="DISCORD_CHANNEL_ID", description="Environment variable for a specific channel ID where all non-bot messages should be processed.")
    max_message_history: int = Field(default=2, description="Maximum number of messages to keep in history per conversation for LLM context.")
    
    # Loaded at runtime
    bot_token: Optional[str] = None
    deferral_channel_id: Optional[int] = None
    wa_user_id: Optional[str] = None
    monitored_channel_id: Optional[int] = None

    def load_env_vars(self):
        self.bot_token = os.getenv(self.bot_token_env_var)
        
        deferral_id_str = os.getenv(self.deferral_channel_id_env_var)
        if deferral_id_str and deferral_id_str.isdigit():
            self.deferral_channel_id = int(deferral_id_str)
            
        wa_user_id_str = os.getenv(self.wa_user_id_env_var, DEFAULT_WA)
        if wa_user_id_str and wa_user_id_str.isdigit():
            self.wa_user_id = wa_user_id_str
        else:
            self.wa_user_id = DEFAULT_WA
            
        monitored_channel_id_str = os.getenv(self.monitored_channel_id_env_var)
        if monitored_channel_id_str and monitored_channel_id_str.isdigit():
            self.monitored_channel_id = int(monitored_channel_id_str)

        if not self.bot_token:
            logger.error(f"Discord bot token not found in env var: {self.bot_token_env_var}")
            raise ValueError(f"Missing Discord bot token: {self.bot_token_env_var}")
        # Warnings for optional IDs
        if not self.deferral_channel_id:
            logger.warning(f"Discord deferral channel ID not found or invalid in env var: {self.deferral_channel_id_env_var}. Deferral reporting may fail.")
        if not self.wa_user_id:
            logger.warning(f"Discord WA User ID not found or invalid in env var: {self.wa_user_id_env_var}. WA corrections via DM may not work.")
        if not self.monitored_channel_id:
            logger.warning(f"Specific monitored channel ID not found or invalid in env var: {self.monitored_channel_id_env_var}. Bot will only respond to DMs and mentions.")


def _truncate_discord_message(message: str, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
    """Truncates a message to fit within Discord's character limit."""
    if len(message) <= limit:
        return message
    return message[:limit-3] + "..."
