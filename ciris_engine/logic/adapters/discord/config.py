"""Configuration schema for Discord adapter."""

from pydantic import BaseModel, Field
from typing import List, Optional
import discord
from pydantic import Field

class DiscordAdapterConfig(BaseModel):
    """Configuration for the Discord adapter."""
    
    bot_token: Optional[str] = Field(default=None, description="Discord bot token")
    
    monitored_channel_ids: List[str] = Field(default_factory=list, description="List of Discord channel IDs to monitor for incoming messages")
    home_channel_id: Optional[str] = Field(default=None, description="Home channel ID for wakeup and primary agent communication")
    deferral_channel_id: Optional[str] = Field(default=None, description="Channel ID for Discord deferrals and guidance from WA")
    
    respond_to_mentions: bool = Field(default=True, description="Respond when the bot is mentioned")
    respond_to_dms: bool = Field(default=True, description="Respond to direct messages")
    
    max_message_length: int = Field(default=2000, description="Maximum Discord message length")
    enable_threads: bool = Field(default=True, description="Enable thread creation for long conversations")
    delete_commands: bool = Field(default=False, description="Delete user commands after processing")
    
    message_rate_limit: float = Field(default=1.0, description="Minimum seconds between messages")
    max_messages_per_minute: int = Field(default=30, description="Maximum messages per minute")
    
    allowed_user_ids: List[str] = Field(default_factory=list, description="List of allowed user IDs (empty = all users)")
    allowed_role_ids: List[str] = Field(default_factory=list, description="List of allowed role IDs")
    admin_user_ids: List[str] = Field(default_factory=list, description="List of admin user IDs with elevated permissions")
    
    status: str = Field(default="online", description="Bot status: online, idle, dnd, invisible")
    activity_type: str = Field(default="watching", description="Activity type: playing, watching, listening, streaming")
    activity_name: str = Field(default="for ethical dilemmas", description="Activity description")
    
    enable_message_content: bool = Field(default=True, description="Enable message content intent")
    enable_guild_messages: bool = Field(default=True, description="Enable guild messages intent")
    enable_dm_messages: bool = Field(default=True, description="Enable DM messages intent")
    
    def get_intents(self) -> discord.Intents:
        """Get Discord intents based on configuration."""
        intents = discord.Intents.default()
        intents.message_content = self.enable_message_content
        intents.guild_messages = self.enable_guild_messages
        intents.dm_messages = self.enable_dm_messages
        return intents
    
    def get_activity(self) -> Optional[discord.Activity]:
        """Get Discord activity based on configuration."""
        if not self.activity_name:
            return None
            
        activity_type_map = {
            "playing": discord.ActivityType.playing,
            "watching": discord.ActivityType.watching,
            "listening": discord.ActivityType.listening,
            "streaming": discord.ActivityType.streaming,
        }
        
        activity_type = activity_type_map.get(self.activity_type.lower(), discord.ActivityType.watching)
        return discord.Activity(type=activity_type, name=self.activity_name)
    
    def get_status(self) -> discord.Status:
        """Get Discord status based on configuration."""
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.dnd,
            "invisible": discord.Status.invisible,
        }
        return status_map.get(self.status.lower(), discord.Status.online)
    
    def get_home_channel_id(self) -> Optional[str]:
        """Get the home channel ID for this Discord adapter."""
        if self.home_channel_id:
            return self.home_channel_id
        if self.monitored_channel_ids:
            return self.monitored_channel_ids[0]  # Default to first monitored channel if no explicit home channel
        return None

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.logic.config.env_utils import get_env_var
        
        # Bot token
        env_token = get_env_var("DISCORD_BOT_TOKEN")
        if env_token:
            self.bot_token = env_token
            
        # Home channel ID
        env_home_channel = get_env_var("DISCORD_HOME_CHANNEL_ID")
        if env_home_channel:
            self.home_channel_id = env_home_channel
            if env_home_channel not in self.monitored_channel_ids:
                self.monitored_channel_ids.append(env_home_channel)
                
        # Legacy support for DISCORD_CHANNEL_ID -> home channel
        env_legacy_channel = get_env_var("DISCORD_CHANNEL_ID")
        if env_legacy_channel and not self.home_channel_id:
            self.home_channel_id = env_legacy_channel
            if env_legacy_channel not in self.monitored_channel_ids:
                self.monitored_channel_ids.append(env_legacy_channel)
                
        env_channels = get_env_var("DISCORD_CHANNEL_IDS")
        if env_channels:
            # Expect comma-separated list
            channel_list = [ch.strip() for ch in env_channels.split(",") if ch.strip()]
            self.monitored_channel_ids.extend(channel_list)
            
        env_deferral = get_env_var("DISCORD_DEFERRAL_CHANNEL_ID")
        if env_deferral:
            self.deferral_channel_id = env_deferral
            
        # User permissions
        env_admin = get_env_var("WA_USER_ID")
        if env_admin:
            if env_admin not in self.admin_user_ids:
                self.admin_user_ids.append(env_admin)
                
    
    def load_env_vars_with_instance(self, instance_id: str) -> None:
        """Load configuration from environment variables with instance-specific prefix."""
        from ciris_engine.logic.config.env_utils import get_env_var
        
        self.load_env_vars()
        
        instance_upper = instance_id.upper()
        
        env_token = get_env_var(f"DISCORD_{instance_upper}_BOT_TOKEN") or get_env_var(f"DISCORD_BOT_TOKEN_{instance_upper}")
        if env_token:
            self.bot_token = env_token
            
        env_home_channel = get_env_var(f"DISCORD_{instance_upper}_HOME_CHANNEL_ID") or get_env_var(f"DISCORD_HOME_CHANNEL_ID_{instance_upper}")
        if env_home_channel:
            self.home_channel_id = env_home_channel
            if env_home_channel not in self.monitored_channel_ids:
                self.monitored_channel_ids.append(env_home_channel)
                
        env_channels = get_env_var(f"DISCORD_{instance_upper}_CHANNEL_IDS") or get_env_var(f"DISCORD_CHANNEL_IDS_{instance_upper}")
        if env_channels:
            channel_list = [ch.strip() for ch in env_channels.split(",") if ch.strip()]
            self.monitored_channel_ids.extend(channel_list)
            
        env_deferral = get_env_var(f"DISCORD_{instance_upper}_DEFERRAL_CHANNEL_ID") or get_env_var(f"DISCORD_DEFERRAL_CHANNEL_ID_{instance_upper}")
        if env_deferral:
            self.deferral_channel_id = env_deferral
            
        env_admin = get_env_var(f"WA_{instance_upper}_USER_ID") or get_env_var(f"WA_USER_ID_{instance_upper}")
        if env_admin:
            if env_admin not in self.admin_user_ids:
                self.admin_user_ids.append(env_admin)
                
