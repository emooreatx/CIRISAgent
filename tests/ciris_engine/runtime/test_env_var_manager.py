"""Tests for the environment variable manager component."""
import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from datetime import datetime, timezone

from ciris_engine.runtime.env_var_manager import EnvVarManager


class TestEnvVarManager:
    """Test the EnvVarManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create an env var manager with temporary .env file."""
        env_file = tmp_path / ".env"
        with patch('ciris_engine.runtime.env_var_manager.Path') as mock_path:
            mock_path.return_value = env_file
            manager = EnvVarManager()
            manager._env_file = env_file
            return manager

    @pytest.fixture
    def sample_env_file(self, tmp_path):
        """Create a sample .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=value1\nANOTHER_VAR=value2\n")
        return env_file

    @pytest.mark.asyncio
    async def test_set_env_var_no_persist(self, manager):
        """Test setting environment variable without persistence."""
        original_value = os.environ.get("TEST_VAR")
        
        try:
            result = await manager.set_env_var("TEST_VAR", "test_value", persist=False)
            
            assert result.success is True
            assert result.operation == "set_env_var"
            assert result.variable_name == "TEST_VAR"
            assert "successfully" in result.message
            assert os.environ["TEST_VAR"] == "test_value"
            assert not manager._env_file.exists()
        finally:
            # Cleanup
            if original_value is None:
                os.environ.pop("TEST_VAR", None)
            else:
                os.environ["TEST_VAR"] = original_value

    @pytest.mark.asyncio
    async def test_set_env_var_with_persist(self, manager):
        """Test setting environment variable with persistence."""
        result = await manager.set_env_var("PERSISTED_VAR", "persisted_value", persist=True)
        
        assert result.success is True
        assert manager._env_file.exists()
        
        content = manager._env_file.read_text()
        assert "PERSISTED_VAR=persisted_value" in content

    @pytest.mark.asyncio
    async def test_set_env_var_update_existing(self, manager, sample_env_file):
        """Test updating existing environment variable in .env file."""
        manager._env_file = sample_env_file
        
        result = await manager.set_env_var("EXISTING_VAR", "new_value", persist=True)
        
        assert result.success is True
        content = manager._env_file.read_text()
        assert "EXISTING_VAR=new_value" in content
        assert "EXISTING_VAR=value1" not in content
        assert "ANOTHER_VAR=value2" in content  # Other vars unchanged

    @pytest.mark.asyncio
    async def test_set_env_var_with_callback(self, manager):
        """Test setting env var with reload callback."""
        callback = AsyncMock()
        
        result = await manager.set_env_var(
            "CALLBACK_VAR", "value", 
            persist=False, 
            reload_config_callback=callback
        )
        
        assert result.success is True
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_env_var_error_handling(self, manager):
        """Test error handling in set_env_var."""
        # Mock the persist method to raise an exception
        with patch.object(manager, '_persist_env_var', side_effect=PermissionError("Permission denied")):
            result = await manager.set_env_var("ERROR_VAR", "value", persist=True)
            
            assert result.success is False
            assert "Permission denied" in result.error

    @pytest.mark.asyncio
    async def test_delete_env_var_exists(self, manager):
        """Test deleting existing environment variable."""
        os.environ["DELETE_ME"] = "value"
        
        result = await manager.delete_env_var("DELETE_ME", persist=False)
        
        assert result.success is True
        assert result.operation == "delete_env_var"
        assert "DELETE_ME" not in os.environ

    @pytest.mark.asyncio
    async def test_delete_env_var_not_exists(self, manager):
        """Test deleting non-existent environment variable."""
        result = await manager.delete_env_var("NON_EXISTENT", persist=False)
        
        assert result.success is True  # Should succeed even if var doesn't exist

    @pytest.mark.asyncio
    async def test_delete_env_var_from_file(self, manager, sample_env_file):
        """Test removing environment variable from .env file."""
        manager._env_file = sample_env_file
        
        result = await manager.delete_env_var("EXISTING_VAR", persist=True)
        
        assert result.success is True
        content = manager._env_file.read_text()
        assert "EXISTING_VAR" not in content
        assert "ANOTHER_VAR=value2" in content  # Other vars remain

    @pytest.mark.asyncio
    async def test_delete_env_var_file_not_exists(self, manager):
        """Test deleting from non-existent .env file."""
        result = await manager.delete_env_var("SOME_VAR", persist=True)
        
        assert result.success is True
        assert not manager._env_file.exists()

    @pytest.mark.asyncio
    async def test_delete_env_var_with_callback(self, manager):
        """Test deleting env var with reload callback."""
        callback = AsyncMock()
        
        result = await manager.delete_env_var(
            "CALLBACK_VAR", 
            persist=False,
            reload_config_callback=callback
        )
        
        assert result.success is True
        callback.assert_called_once()

    def test_get_env_vars_empty(self, manager):
        """Test getting env vars from non-existent file."""
        env_vars = manager.get_env_vars()
        assert env_vars == []

    def test_get_env_vars_from_file(self, manager, sample_env_file):
        """Test getting env vars from file."""
        manager._env_file = sample_env_file
        
        env_vars = manager.get_env_vars()
        assert len(env_vars) == 2
        assert ("EXISTING_VAR", "value1") in env_vars
        assert ("ANOTHER_VAR", "value2") in env_vars

    def test_get_env_vars_ignores_comments(self, manager, tmp_path):
        """Test that comments and empty lines are ignored."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
# This is a comment
VAR1=value1

# Another comment
VAR2=value2
INVALID_LINE_NO_EQUALS
VAR3=value=with=equals
""")
        manager._env_file = env_file
        
        env_vars = manager.get_env_vars()
        assert len(env_vars) == 3
        assert ("VAR1", "value1") in env_vars
        assert ("VAR2", "value2") in env_vars
        assert ("VAR3", "value=with=equals") in env_vars

    @pytest.mark.asyncio
    async def test_persist_env_var_special_chars(self, manager):
        """Test persisting env vars with special characters."""
        await manager._persist_env_var("SPECIAL_VAR", "value with spaces and = signs")
        
        content = manager._env_file.read_text()
        assert "SPECIAL_VAR=value with spaces and = signs" in content