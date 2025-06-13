"""Tests for the configuration backup manager component."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from ciris_engine.runtime.config_backup_manager import ConfigBackupManager


class TestConfigBackupManager:
    """Test the ConfigBackupManager class."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a backup manager with temporary directory."""
        backup_dir = tmp_path / "test_backups"
        return ConfigBackupManager(backup_dir)

    @pytest.fixture
    def sample_config_files(self, tmp_path):
        """Create sample config files for testing."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        
        # Create sample config files
        (config_dir / "base.yaml").write_text("base_config: true")
        (config_dir / "development.yaml").write_text("dev_config: true")
        
        profiles_dir = tmp_path / "ciris_profiles"
        profiles_dir.mkdir()
        (profiles_dir / "default.yaml").write_text("profile: default")
        (profiles_dir / "test.yaml").write_text("profile: test")
        
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_VAR=value")
        
        return tmp_path

    @pytest.mark.asyncio
    async def test_backup_config_minimal(self, manager):
        """Test basic backup without any files."""
        # Mock the backup manager's Path operations to avoid real file system
        with patch('ciris_engine.runtime.config_backup_manager.Path') as mock_path_class:
            def path_side_effect(path_str):
                mock_p = MagicMock()
                if path_str.startswith("config/") or path_str == "ciris_profiles" or path_str == ".env":
                    mock_p.exists.return_value = False
                else:
                    mock_p.exists.return_value = True
                return mock_p
            
            mock_path_class.side_effect = path_side_effect
            
            result = await manager.backup_config()
            
            assert result.success is True
            assert result.operation == "backup_config"
            assert result.backup_name.startswith("config_backup_")
            assert len(result.files_included) == 0
            
            # Check backup directory created
            backup_path = manager._backup_dir / result.backup_name
            assert backup_path.exists()
            
            # Check metadata file
            metadata_file = backup_path / "backup_metadata.json"
            assert metadata_file.exists()

    @pytest.mark.asyncio
    async def test_backup_config_with_files(self, manager, sample_config_files):
        """Test backup with actual config files."""
        # Patch Path in the module where it's used
        with patch('ciris_engine.runtime.config_backup_manager.Path') as mock_path, \
             patch('shutil.copy2') as mock_copy, \
             patch('shutil.copytree') as mock_copytree:
            
            def path_side_effect(path_str):
                if path_str == "config/base.yaml":
                    return sample_config_files / "config" / "base.yaml"
                elif path_str == "config/development.yaml":
                    return sample_config_files / "config" / "development.yaml"
                elif path_str == "config/production.yaml":
                    return sample_config_files / "config" / "production.yaml"
                elif path_str == "ciris_profiles":
                    return sample_config_files / "ciris_profiles"
                elif path_str == ".env":
                    return sample_config_files / ".env"
                else:
                    # Return a proper Path object for other paths
                    return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            result = await manager.backup_config(
                include_profiles=True,
                include_env_vars=True,
                backup_name="test_backup"
            )
        
        assert result.success is True
        assert result.backup_name == "test_backup"
        assert len(result.files_included) > 0
        
        # Verify copy operations were called
        assert mock_copy.call_count >= 2  # At least base.yaml and development.yaml
        mock_copytree.assert_called_once()  # For profiles directory

    @pytest.mark.asyncio
    async def test_backup_config_profiles_only(self, manager, sample_config_files):
        """Test backup including only profiles."""
        with patch('ciris_engine.runtime.config_backup_manager.Path') as mock_path:
            def path_side_effect(path_str):
                if path_str.startswith("config/"):
                    # Return non-existent paths for config files
                    mock_non_existent = MagicMock()
                    mock_non_existent.exists.return_value = False
                    return mock_non_existent
                elif path_str == "ciris_profiles":
                    return sample_config_files / "ciris_profiles"
                elif path_str == ".env":
                    mock_non_existent = MagicMock()
                    mock_non_existent.exists.return_value = False
                    return mock_non_existent
                else:
                    return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            result = await manager.backup_config(
                include_profiles=True,
                include_env_vars=False
            )
        
        assert result.success is True
        assert any("ciris_profiles" in f for f in result.files_included)
        assert not any(".env" in f for f in result.files_included)

    @pytest.mark.asyncio
    async def test_backup_config_error_handling(self, manager):
        """Test backup error handling."""
        with patch('shutil.copy2', side_effect=PermissionError("Access denied")):
            result = await manager.backup_config()
            
        assert result.success is False
        assert "Access denied" in result.error

    @pytest.mark.asyncio
    async def test_restore_config_success(self, manager, sample_config_files):
        """Test successful config restoration."""
        # First create a backup
        backup_name = "restore_test"
        backup_path = manager._backup_dir / backup_name
        backup_path.mkdir()
        
        # Create backup files
        (backup_path / "base.yaml").write_text("restored_base: true")
        (backup_path / "development.yaml").write_text("restored_dev: true")
        
        profiles_backup = backup_path / "ciris_profiles"
        profiles_backup.mkdir()
        (profiles_backup / "restored.yaml").write_text("restored_profile: true")
        
        (backup_path / ".env").write_text("RESTORED_VAR=value")
        
        # Create metadata
        metadata = {
            "backup_name": backup_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "files_included": ["config/base.yaml", "ciris_profiles/restored.yaml"],
            "include_profiles": True,
            "include_env_vars": True
        }
        with open(backup_path / "backup_metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        # Mock file system for restoration
        with patch('ciris_engine.runtime.config_backup_manager.Path') as mock_path, \
             patch('shutil.copy2') as mock_copy:
            
            def path_side_effect(path_str):
                if path_str == "config":
                    mock_config_dir = MagicMock()
                    mock_config_dir.mkdir = MagicMock()
                    return mock_config_dir
                elif path_str == "ciris_profiles":
                    mock_profiles_dir = MagicMock()
                    mock_profiles_dir.mkdir = MagicMock()
                    return mock_profiles_dir
                else:
                    return Path(path_str)
            
            mock_path.side_effect = path_side_effect
            
            result = await manager.restore_config(backup_name)
        
        assert result.success is True
        assert result.backup_name == backup_name
        assert result.operation == "restore_config"

    @pytest.mark.asyncio
    async def test_restore_config_not_found(self, manager):
        """Test restoring non-existent backup."""
        result = await manager.restore_config("non_existent_backup")
        
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_restore_config_no_metadata(self, manager):
        """Test restoring backup without metadata."""
        backup_name = "no_metadata"
        backup_path = manager._backup_dir / backup_name
        backup_path.mkdir()
        
        result = await manager.restore_config(backup_name)
        
        assert result.success is False
        assert "metadata not found" in result.error

    @pytest.mark.asyncio
    async def test_restore_config_selective(self, manager):
        """Test selective restoration."""
        backup_name = "selective_test"
        backup_path = manager._backup_dir / backup_name
        backup_path.mkdir()
        
        # Create metadata indicating both profiles and env vars were backed up
        metadata = {
            "backup_name": backup_name,
            "include_profiles": True,
            "include_env_vars": True
        }
        with open(backup_path / "backup_metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        with patch('shutil.copy2') as mock_copy:
            result = await manager.restore_config(
                backup_name,
                restore_profiles=True,
                restore_env_vars=False
            )
        
        assert result.success is True

    def test_list_backups_empty(self, manager):
        """Test listing backups when none exist."""
        backups = manager.list_backups()
        assert backups == []

    def test_list_backups_with_backups(self, manager):
        """Test listing backups with existing backups."""
        # Create sample backups
        backup1_path = manager._backup_dir / "backup1"
        backup1_path.mkdir()
        metadata1 = {
            "backup_name": "backup1",
            "timestamp": "2024-01-01T10:00:00+00:00"
        }
        with open(backup1_path / "backup_metadata.json", 'w') as f:
            json.dump(metadata1, f)
        
        backup2_path = manager._backup_dir / "backup2"
        backup2_path.mkdir()
        metadata2 = {
            "backup_name": "backup2", 
            "timestamp": "2024-01-01T11:00:00+00:00"
        }
        with open(backup2_path / "backup_metadata.json", 'w') as f:
            json.dump(metadata2, f)
        
        backups = manager.list_backups()
        assert len(backups) == 2
        # Should be sorted by timestamp (newest first)
        assert backups[0]["backup_name"] == "backup2"
        assert backups[1]["backup_name"] == "backup1"

    def test_list_backups_ignores_invalid(self, manager):
        """Test that invalid backup directories are ignored."""
        # Create backup without metadata
        invalid_backup = manager._backup_dir / "invalid"
        invalid_backup.mkdir()
        
        # Create valid backup
        valid_backup = manager._backup_dir / "valid"
        valid_backup.mkdir()
        metadata = {"backup_name": "valid", "timestamp": "2024-01-01T10:00:00+00:00"}
        with open(valid_backup / "backup_metadata.json", 'w') as f:
            json.dump(metadata, f)
        
        backups = manager.list_backups()
        assert len(backups) == 1
        assert backups[0]["backup_name"] == "valid"