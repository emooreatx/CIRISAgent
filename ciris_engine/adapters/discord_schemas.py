from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class DiscordMessage(BaseModel):
    """Discord message schema for adapter use."""
    message_id: str
    author_id: str
    author_name: str
    content: str
    channel_id: str
    guild_id: Optional[str] = None
    reference_message_id: Optional[str] = None
    timestamp: datetime
    is_bot: bool = False
    is_dm: bool = False

class DiscordConfig(BaseModel):
    """Discord adapter configuration."""
    bot_token_env_var: str = Field(default="DISCORD_BOT_TOKEN")
    deferral_channel_id_env_var: str = Field(default="DISCORD_DEFERRAL_CHANNEL_ID") 
    wa_user_id_env_var: str = Field(default="DISCORD_WA_USER_ID")
    monitored_channel_id_env_var: str = Field(default="DISCORD_CHANNEL_ID")
    max_message_history: int = Field(default=2)
    message_limit: int = Field(default=2000)
    
    # Runtime loaded values
    bot_token: Optional[str] = None
    deferral_channel_id: Optional[int] = None
    wa_user_id: Optional[str] = None
    monitored_channel_id: Optional[int] = None

    def load_env_vars(self):
        """Load values from environment variables."""
        import os
        self.bot_token = os.getenv(self.bot_token_env_var)
        
        deferral_id = os.getenv(self.deferral_channel_id_env_var)
        if deferral_id and deferral_id.isdigit():
            self.deferral_channel_id = int(deferral_id)
            
        self.wa_user_id = os.getenv(self.wa_user_id_env_var)
        
        channel_id = os.getenv(self.monitored_channel_id_env_var)
        if channel_id and channel_id.isdigit():
            self.monitored_channel_id = int(channel_id)
