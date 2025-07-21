"""
Tests for nginx configuration management.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import tempfile

from ciris_manager.nginx_manager import NginxManager


class TestNginxManager:
    """Test nginx configuration management."""
    
    @pytest.fixture
    def temp_config(self):
        """Create a temporary nginx config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write("""
upstream datum {
    server 127.0.0.1:8080;
}

upstream ciris_gui {
    server 127.0.0.1:3000;
}

# === CIRISMANAGER UPSTREAMS START ===
# === CIRISMANAGER UPSTREAMS END ===

server {
    listen 443 ssl;
    
    # === CIRISMANAGER OAUTH ROUTES START ===
    # === CIRISMANAGER OAUTH ROUTES END ===
    
    # Default API endpoint
    location /v1/ {
        proxy_pass http://datum;
    }
    
    # === CIRISMANAGER API ROUTES START ===
    # === CIRISMANAGER API ROUTES END ===
    
    # GUI (React app)
    location / {
        proxy_pass http://ciris_gui;
    }
}
""")
            return Path(f.name)
    
    @pytest.fixture
    def nginx_manager(self, temp_config):
        """Create nginx manager with temp config."""
        return NginxManager(
            config_path=str(temp_config),
            reload_command="echo reload"
        )
    
    def test_init(self, nginx_manager, temp_config):
        """Test initialization."""
        assert nginx_manager.config_path == temp_config
        assert nginx_manager.reload_command == "echo reload"
    
    def test_get_configured_agents(self, nginx_manager):
        """Test parsing existing agents."""
        agents = nginx_manager.get_configured_agents()
        assert agents == {"datum": 8080}
        # ciris_gui should be excluded
        assert "ciris_gui" not in agents
    
    @patch('subprocess.run')
    def test_add_agent_route(self, mock_run, nginx_manager, temp_config):
        """Test adding agent route."""
        # Mock nginx test and reload
        mock_run.return_value = MagicMock(returncode=0)
        
        # Add agent
        result = nginx_manager.add_agent_route("scout", 8081, "Scout")
        assert result is True
        
        # Check config was updated
        content = temp_config.read_text()
        
        # Check upstream was added
        assert "upstream scout {" in content
        assert "server 127.0.0.1:8081;" in content
        
        # Check OAuth route was added
        assert "/v1/auth/oauth/scout/" in content
        
        # Check API route was added
        assert "# Scout API (port 8081)" in content
        assert "/api/scout/" in content
        
        # Verify nginx test and reload were called
        assert mock_run.call_count == 2
        nginx_calls = [call.args[0] for call in mock_run.call_args_list]
        assert ["nginx", "-t"] in nginx_calls
        assert ["echo", "reload"] in nginx_calls
    
    @patch('subprocess.run')
    def test_remove_agent_route(self, mock_run, nginx_manager, temp_config):
        """Test removing agent route."""
        # First add an agent
        mock_run.return_value = MagicMock(returncode=0)
        nginx_manager.add_agent_route("scout", 8081)
        
        # Reset mock
        mock_run.reset_mock()
        
        # Remove agent
        result = nginx_manager.remove_agent_route("scout")
        assert result is True
        
        # Check config was updated
        content = temp_config.read_text()
        
        # Check upstream was removed
        assert "upstream scout {" not in content
        assert "server 127.0.0.1:8081;" not in content
        
        # Check routes were removed
        assert "/v1/auth/oauth/scout/" not in content
        assert "/api/scout/" not in content
        
        # Original datum should still be there
        assert "upstream datum {" in content
    
    @patch('subprocess.run')
    def test_add_duplicate_agent(self, mock_run, nginx_manager):
        """Test adding duplicate agent."""
        mock_run.return_value = MagicMock(returncode=0)
        
        # Add agent once
        result = nginx_manager.add_agent_route("scout", 8081)
        assert result is True
        
        # Try to add again - should succeed (idempotent)
        result = nginx_manager.add_agent_route("scout", 8081)
        assert result is True
    
    @patch('subprocess.run')
    def test_nginx_test_failure(self, mock_run, nginx_manager, temp_config):
        """Test handling nginx test failure."""
        # Mock nginx test failure
        mock_run.return_value = MagicMock(returncode=1)
        
        # Try to add agent
        result = nginx_manager.add_agent_route("scout", 8081)
        assert result is False
        
        # Check original config was restored
        content = temp_config.read_text()
        assert "upstream scout {" not in content
    
    def test_ensure_managed_sections(self, nginx_manager):
        """Test ensuring managed sections exist."""
        # Sections should already exist in fixture
        result = nginx_manager.ensure_managed_sections()
        assert result is True
    
    def test_ensure_managed_sections_missing(self, nginx_manager):
        """Test adding missing managed sections."""
        # Create config without sections
        nginx_manager.config_path.write_text("""
upstream datum {
    server 127.0.0.1:8080;
}

upstream ciris_gui {
    server 127.0.0.1:3000;
}

server {
    listen 443 ssl;
    
    # Default API endpoint
    location /v1/ {
        proxy_pass http://datum;
    }
    
    # GUI (React app)
    location / {
        proxy_pass http://ciris_gui;
    }
}
""")
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            result = nginx_manager.ensure_managed_sections()
            assert result is True
            
            content = nginx_manager.config_path.read_text()
            assert "# === CIRISMANAGER UPSTREAMS START ===" in content
            assert "# === CIRISMANAGER OAUTH ROUTES START ===" in content
            assert "# === CIRISMANAGER API ROUTES START ===" in content
    
    def test_backup_restore(self, nginx_manager, temp_config):
        """Test backup and restore functionality."""
        original_content = temp_config.read_text()
        
        # Create backup
        nginx_manager._backup_config()
        
        # Modify config
        temp_config.write_text("modified content")
        
        # Restore backup
        nginx_manager._restore_backup()
        
        # Check content was restored
        assert temp_config.read_text() == original_content
        
        # Check backup file exists
        backup_files = list(temp_config.parent.glob(f"{temp_config.name}.bak.*"))
        assert len(backup_files) >= 1
        
        # Clean up backup files
        for backup in backup_files:
            backup.unlink()
    
    def teardown_method(self, method):
        """Clean up temp files after each test."""
        # Clean up any backup files
        import glob
        import os
        for backup in glob.glob("*.conf.bak.*"):
            os.unlink(backup)