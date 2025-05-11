"""Configuration settings for CIRIS Discord Agent."""

import os
import logging
from typing import Optional, Set

# LLM Configuration - These act as defaults or can be used by other parts of the module
DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL_NAME = "gpt-4o-mini"

# Define actual configuration variables at module level for direct import
# Check for OPENAI_API_BASE, then OPENAI_BASE_URL, then use default.
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", DEFAULT_API_BASE)
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", DEFAULT_MODEL_NAME)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Guardrail thresholds
ENTROPY_THRESHOLD = 0.40
COHERENCE_THRESHOLD = 0.80

# Error message prefix
ERROR_PREFIX_CIRIS = "CIRIS ERROR:"

# Default Discord channel and server IDs
DEFAULT_SERVER_ID = '1364300186003968060'
DEFAULT_CHANNEL_ID = '1365904496286498836'
DEFAULT_DEFERRAL_CHANNEL_ID = '1366079806893985963'

class DiscordConfig:
    """Discord configuration with proper validation."""
    
    def __init__(self):
        # Discord configuration
        self.token = os.environ.get("DISCORD_BOT_TOKEN")
        self.server_id = os.environ.get("DISCORD_SERVER_ID", DEFAULT_SERVER_ID)
        self.server_id_int = int(self.server_id) if self.server_id else None
        
        # Channel configuration
        channel_ids_val = os.environ.get("DISCORD_CHANNEL_ID", DEFAULT_CHANNEL_ID)
        self.target_channel_ids = channel_ids_val.split(',') if channel_ids_val else None
        self.target_channels_set: Optional[Set[int]] = (
            set(int(cid) for cid in self.target_channel_ids) if self.target_channel_ids else None
        )
        
        # Deferral channel configuration
        self.deferral_channel_id = os.environ.get("DISCORD_DEFERRAL_CHANNEL", DEFAULT_DEFERRAL_CHANNEL_ID)
        
        # OpenAI configuration 
        # Use the module-level variables defined above
        self.openai_api_key = OPENAI_API_KEY
        self.openai_api_base = OPENAI_API_BASE # This will now use the updated logic
        self.model_name = OPENAI_MODEL_NAME
    
    def validate(self) -> bool:
        """Validate if configuration is sufficient to run agent."""
        if not self.token:
            logging.error("DISCORD_BOT_TOKEN environment variable not set.")
            return False
            
        if not self.openai_api_key:
            logging.error("OPENAI_API_KEY environment variable not set.")
            return False
            
        if not self.target_channel_ids:
            logging.error("No target channels specified.")
            return False
            
        return True
    
    def log_config(self) -> None:
        """Log the current configuration for debugging."""
        if self.server_id:
            logging.info(f"Targeting server ID: {self.server_id}")
        else:
            logging.info("Not targeting a specific server.")

        if self.target_channel_ids:
            logging.info(f"Targeting channels: {self.target_channel_ids}")
        else:
            logging.info("Not targeting specific channels.")
            
        if self.deferral_channel_id:
            logging.info(f"Targeting deferral channel ID: {self.deferral_channel_id}")
