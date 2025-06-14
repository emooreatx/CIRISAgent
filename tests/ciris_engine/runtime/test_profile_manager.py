"""Tests for the profile manager component."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from ciris_engine.utils.profile_manager import ProfileManager
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile


class TestProfileManager:
    """Test the ProfileManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a profile manager with temporary directory."""
        with patch('ciris_engine.utils.profile_manager.Path') as mock_path:
            mock_path.return_value = tmp_path / "ciris_profiles"
            manager = ProfileManager()
            manager._profiles_dir = tmp_path / "ciris_profiles"
            manager._profiles_dir.mkdir(exist_ok=True)
            return manager

    @pytest.fixture
    def sample_profile_data(self):
        """Sample profile data for testing."""
        return {
            "name": "test_profile",
            "description": "Test profile",
            "permitted_actions": ["OBSERVE", "SPEAK"],
            "discord_config": {"enabled": True},
            "api_config": {"enabled": False},
            "cli_config": {"enabled": True}
        }

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, manager):
        """Test listing profiles when none exist."""
        profiles = await manager.list_profiles()
        assert profiles == []

    @pytest.mark.asyncio
    async def test_list_profiles_with_profiles(self, manager, sample_profile_data):
        """Test listing profiles with existing profiles."""
        # Create a test profile file
        profile_file = manager._profiles_dir / "test_profile.yaml"
        import yaml
        with open(profile_file, 'w') as f:
            yaml.safe_dump(sample_profile_data, f)

        # Mock load_profile to return a valid profile
        mock_profile = MagicMock()
        mock_profile.description = "Test profile"
        mock_profile.permitted_actions = [MagicMock(value="OBSERVE"), MagicMock(value="SPEAK")]
        mock_profile.discord_config = {"enabled": True}
        mock_profile.api_config = {"enabled": False}
        mock_profile.cli_config = {"enabled": True}

        with patch('ciris_engine.utils.profile_manager.load_profile', return_value=mock_profile):
            profiles = await manager.list_profiles()
            
        assert len(profiles) == 1
        assert profiles[0].name == "test_profile"
        assert profiles[0].description == "Test profile"
        assert profiles[0].permitted_actions == ["OBSERVE", "SPEAK"]

    @pytest.mark.asyncio
    async def test_list_profiles_with_error(self, manager):
        """Test listing profiles handles load errors gracefully."""
        # Create a test profile file
        profile_file = manager._profiles_dir / "bad_profile.yaml"
        profile_file.write_text("invalid: yaml: content:")

        with patch('ciris_engine.utils.profile_manager.load_profile', side_effect=Exception("Parse error")):
            profiles = await manager.list_profiles()
            
        assert len(profiles) == 1
        assert profiles[0].name == "bad_profile"
        assert "Error loading profile" in profiles[0].description
        assert profiles[0].is_active is False

    @pytest.mark.asyncio
    async def test_create_profile_valid(self, manager):
        """Test creating a valid profile."""
        # Mock AgentProfile validation to pass
        with patch('ciris_engine.utils.profile_manager.AgentProfile') as mock_agent_profile:
            mock_agent_profile.return_value = MagicMock()
            
            config = {
                "permitted_actions": ["OBSERVE", "SPEAK", "TOOL"],
                "system_prompt": "Test system prompt"
            }
            
            result = await manager.create_profile(
                name="new_profile",
                config=config,
                description="New test profile",
                save_to_file=True
            )
            
            assert result.success is True
            assert result.profile_name == "new_profile"
            assert "successfully" in result.message
            assert result.profile_info.name == "new_profile"
            
            # Check file was created
            profile_file = manager._profiles_dir / "new_profile.yaml"
            assert profile_file.exists()

    @pytest.mark.asyncio
    async def test_create_profile_invalid(self, manager):
        """Test creating an invalid profile."""
        config = {
            "permitted_actions": "should_be_list_not_string",  # Invalid type
            "temperature": "not_a_number"  # Invalid type if this were an LLM config
        }
        
        result = await manager.create_profile(
            name="bad_profile",
            config=config
        )
        
        assert result.success is False
        assert "validation failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_create_profile_with_base(self, manager, sample_profile_data):
        """Test creating a profile based on another profile."""
        # Mock AgentProfile validation to pass
        with patch('ciris_engine.utils.profile_manager.AgentProfile') as mock_agent_profile:
            mock_agent_profile.return_value = MagicMock()
            
            # Create base profile
            base_file = manager._profiles_dir / "base_profile.yaml"
            import yaml
            with open(base_file, 'w') as f:
                yaml.safe_dump(sample_profile_data, f)
            
            # Create new profile based on it
            config = {
                "permitted_actions": ["OBSERVE", "SPEAK", "MEMORIZE"]  # Override
            }
            
            result = await manager.create_profile(
                name="derived_profile",
                config=config,
                base_profile="base_profile"
            )
            
            assert result.success is True
            
            # Check merged config
            derived_file = manager._profiles_dir / "derived_profile.yaml"
            with open(derived_file, 'r') as f:
                derived_data = yaml.safe_load(f)
            
            assert derived_data["permitted_actions"] == ["OBSERVE", "SPEAK", "MEMORIZE"]
            assert derived_data["discord_config"] == {"enabled": True}  # Inherited

    @pytest.mark.asyncio
    async def test_create_profile_memory_only(self, manager):
        """Test creating a profile without saving to file."""
        # Mock AgentProfile validation to pass
        with patch('ciris_engine.utils.profile_manager.AgentProfile') as mock_agent_profile:
            mock_agent_profile.return_value = MagicMock()
            
            config = {"permitted_actions": ["OBSERVE"]}
            
            result = await manager.create_profile(
                name="memory_profile",
                config=config,
                save_to_file=False
            )
            
            assert result.success is True
            assert result.profile_info.file_path == "memory"
            
            # Check no file was created
            profile_file = manager._profiles_dir / "memory_profile.yaml"
            assert not profile_file.exists()

    def test_add_and_get_loaded_profiles(self, manager):
        """Test tracking loaded profiles."""
        assert manager.get_loaded_profiles() == []
        
        manager.add_loaded_profile("profile1")
        manager.add_loaded_profile("profile2")
        manager.add_loaded_profile("profile1")  # Duplicate
        
        loaded = manager.get_loaded_profiles()
        assert len(loaded) == 2
        assert "profile1" in loaded
        assert "profile2" in loaded

    @pytest.mark.asyncio
    async def test_load_yaml_async(self, manager, tmp_path):
        """Test async YAML loading."""
        test_file = tmp_path / "test.yaml"
        test_data = {"key": "value", "number": 42}
        
        import yaml
        with open(test_file, 'w') as f:
            yaml.safe_dump(test_data, f)
        
        loaded = await manager._load_yaml(test_file)
        assert loaded == test_data

    @pytest.mark.asyncio
    async def test_list_profiles_checks_active_status(self, manager, sample_profile_data):
        """Test that list_profiles correctly identifies active profiles."""
        # Create profile file
        profile_file = manager._profiles_dir / "active_profile.yaml"
        import yaml
        with open(profile_file, 'w') as f:
            yaml.safe_dump(sample_profile_data, f)

        # Mock config with active profile
        mock_config = MagicMock()
        mock_config.agent_profiles = ["active_profile"]

        # Mock load_profile
        mock_profile = MagicMock()
        mock_profile.description = "Test"
        mock_profile.permitted_actions = []

        with patch('ciris_engine.utils.profile_manager.load_profile', return_value=mock_profile):
            profiles = await manager.list_profiles(mock_config)
            
        assert len(profiles) == 1
        assert profiles[0].is_active is True