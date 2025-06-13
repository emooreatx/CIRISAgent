"""
Tests for Discord adapter configuration.
Extracted from test_discord_comprehensive.py to focus on configuration logic.
"""

import pytest
import discord
from unittest.mock import patch, MagicMock

from ciris_engine.adapters.discord.config import DiscordAdapterConfig


class TestDiscordAdapterConfig:
    """Test Discord adapter configuration - central place for all Discord configs"""
    
    def test_config_initialization(self):
        """Test default configuration initialization"""
        config = DiscordAdapterConfig()
        
        # Authentication
        assert config.bot_token is None
        
        # Channel configuration
        assert config.monitored_channel_ids == []
        assert config.home_channel_id is None
        assert config.deferral_channel_id is None
        
        # Bot behavior
        assert config.respond_to_mentions == True
        assert config.respond_to_dms == True
        
        # Message handling
        assert config.max_message_length == 2000
        assert config.enable_threads == True
        assert config.delete_commands == False
        
        # Rate limiting
        assert config.message_rate_limit == 1.0
        assert config.max_messages_per_minute == 30
        
        # Permissions
        assert config.allowed_user_ids == []
        assert config.allowed_role_ids == []
        assert config.admin_user_ids == []
        
        # Status and presence
        assert config.status == "online"
        assert config.activity_type == "watching"
        assert config.activity_name == "for ethical dilemmas"
        
        # Intents
        assert config.enable_message_content == True
        assert config.enable_guild_messages == True
        assert config.enable_dm_messages == True
    
    def test_config_intents(self):
        """Test Discord intents configuration"""
        config = DiscordAdapterConfig()
        intents = config.get_intents()
        
        assert isinstance(intents, discord.Intents)
        assert intents.message_content == True
        assert intents.guild_messages == True
        assert intents.dm_messages == True
        
        # Test custom intents
        config.enable_message_content = False
        intents = config.get_intents()
        assert intents.message_content == False
    
    def test_config_activity(self):
        """Test Discord activity configuration"""
        config = DiscordAdapterConfig()
        activity = config.get_activity()
        
        assert isinstance(activity, discord.Activity)
        assert activity.type == discord.ActivityType.watching
        assert activity.name == "for ethical dilemmas"
        
        # Test different activity types
        config.activity_type = "playing"
        config.activity_name = "chess"
        activity = config.get_activity()
        assert activity.type == discord.ActivityType.playing
        assert activity.name == "chess"
        
        # Test no activity
        config.activity_name = ""
        activity = config.get_activity()
        assert activity is None
    
    def test_config_status(self):
        """Test Discord status configuration"""
        config = DiscordAdapterConfig()
        status = config.get_status()
        
        assert status == discord.Status.online
        
        # Test different statuses
        config.status = "idle"
        assert config.get_status() == discord.Status.idle
        
        config.status = "dnd"
        assert config.get_status() == discord.Status.dnd
        
        config.status = "invisible"
        assert config.get_status() == discord.Status.invisible
        
        # Test invalid status defaults to online
        config.status = "invalid"
        assert config.get_status() == discord.Status.online
    
    def test_config_home_channel(self):
        """Test home channel ID logic"""
        config = DiscordAdapterConfig()
        
        # No channels configured
        assert config.get_home_channel_id() is None
        
        # Home channel set explicitly
        config.home_channel_id = "123456"
        assert config.get_home_channel_id() == "123456"
        
        # No home but monitored channels exist
        config.home_channel_id = None
        config.monitored_channel_ids = ["789012", "345678"]
        assert config.get_home_channel_id() == "789012"
    
    @patch('ciris_engine.config.env_utils.get_env_var')
    def test_config_env_loading(self, mock_get_env):
        """Test loading configuration from environment variables (legacy and new fields)"""
        # Mock environment variables (legacy and new)
        env_vars = {
            'DISCORD_BOT_TOKEN': 'env_token_123',
            'DISCORD_CHANNEL_ID': '123456',  # legacy single channel
            'DISCORD_CHANNEL_IDS': '789012,345678,901234',  # new multi-channel
            'DISCORD_DEFERRAL_CHANNEL_ID': '567890',
            'WA_USER_ID': 'admin_user_123'
        }
        
        def mock_env_get(key):
            return env_vars.get(key)
        
        mock_get_env.side_effect = mock_env_get
        
        config = DiscordAdapterConfig()
        config.load_env_vars()
        
        # Verify all environment variables were loaded and mapped to new fields
        assert config.bot_token == 'env_token_123'
        # home_channel_id should be set from DISCORD_CHANNEL_ID
        assert config.home_channel_id == '123456'
        # monitored_channel_ids should include both legacy and new env values
        expected_channels = {'123456', '789012', '345678', '901234'}
        assert set(config.monitored_channel_ids) == expected_channels
        assert config.deferral_channel_id == '567890'
        assert 'admin_user_123' in config.admin_user_ids
    
    def test_config_permissions(self):
        """Test permission configuration"""
        config = DiscordAdapterConfig()
        
        # Add users and roles
        config.allowed_user_ids = ["user1", "user2"]
        config.allowed_role_ids = ["role1", "role2"]
        config.admin_user_ids = ["admin1", "admin2"]
        
        assert len(config.allowed_user_ids) == 2
        assert len(config.allowed_role_ids) == 2
        assert len(config.admin_user_ids) == 2
        assert "user1" in config.allowed_user_ids
        assert "role1" in config.allowed_role_ids
        assert "admin1" in config.admin_user_ids