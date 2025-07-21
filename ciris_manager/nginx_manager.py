"""
NGINX configuration management for CIRIS agents.

This module handles dynamic nginx configuration updates when agents are
created or removed through CIRISManager.
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class NginxManager:
    """Manages nginx configuration for CIRIS agents."""
    
    # Template for agent upstream block
    UPSTREAM_TEMPLATE = """
upstream {agent_name} {{
    server 127.0.0.1:{port};
}}"""

    # Template for OAuth callback routes
    OAUTH_TEMPLATE = """
    # {agent_display} OAuth callbacks (Direct API pattern)
    location ~ ^/v1/auth/oauth/{agent_name}/(.+)/callback$ {{
        proxy_pass http://{agent_name}/v1/auth/oauth/$1/callback$is_args$args;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}"""

    # Template for agent API routes
    API_ROUTE_TEMPLATE = """
    # {agent_display} API (port {port})
    location ~ ^/api/{agent_name}/(.*)$ {{
        proxy_pass http://{agent_name}/$1$is_args$args;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }}"""

    # Markers for managed sections
    UPSTREAM_START_MARKER = "# === CIRISMANAGER UPSTREAMS START ==="
    UPSTREAM_END_MARKER = "# === CIRISMANAGER UPSTREAMS END ==="
    OAUTH_START_MARKER = "    # === CIRISMANAGER OAUTH ROUTES START ==="
    OAUTH_END_MARKER = "    # === CIRISMANAGER OAUTH ROUTES END ==="
    API_START_MARKER = "    # === CIRISMANAGER API ROUTES START ==="
    API_END_MARKER = "    # === CIRISMANAGER API ROUTES END ==="

    def __init__(self, config_path: str = "/etc/nginx/conf.d/agents.ciris.ai.conf",
                 reload_command: str = "systemctl reload nginx"):
        """
        Initialize nginx manager.
        
        Args:
            config_path: Path to nginx configuration file
            reload_command: Command to reload nginx
        """
        self.config_path = Path(config_path)
        self.reload_command = reload_command
        
    def add_agent_route(self, agent_name: str, port: int, 
                       agent_display: Optional[str] = None) -> bool:
        """
        Add nginx routes for a new agent.
        
        Args:
            agent_name: Agent name (lowercase, used in URLs)
            port: Port number for the agent
            agent_display: Display name for comments (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not agent_display:
            agent_display = agent_name.replace("-", " ").title()
            
        try:
            # Read current config
            if not self.config_path.exists():
                logger.error(f"Nginx config not found at {self.config_path}")
                return False
                
            content = self.config_path.read_text()
            
            # Check if agent already exists
            if f"upstream {agent_name} {{" in content:
                logger.warning(f"Agent {agent_name} already exists in nginx config")
                return True
                
            # Add upstream
            upstream_block = self.UPSTREAM_TEMPLATE.format(
                agent_name=agent_name,
                port=port
            )
            content = self._insert_block(
                content, upstream_block, 
                self.UPSTREAM_START_MARKER, 
                self.UPSTREAM_END_MARKER
            )
            
            # Add OAuth route
            oauth_block = self.OAUTH_TEMPLATE.format(
                agent_name=agent_name,
                agent_display=agent_display
            )
            content = self._insert_block(
                content, oauth_block,
                self.OAUTH_START_MARKER,
                self.OAUTH_END_MARKER
            )
            
            # Add API route
            api_block = self.API_ROUTE_TEMPLATE.format(
                agent_name=agent_name,
                agent_display=agent_display,
                port=port
            )
            content = self._insert_block(
                content, api_block,
                self.API_START_MARKER,
                self.API_END_MARKER
            )
            
            # Backup and write new config
            self._backup_config()
            self.config_path.write_text(content)
            
            # Test and reload nginx
            if self._test_nginx_config():
                if self._reload_nginx():
                    logger.info(f"Successfully added routes for agent {agent_name}")
                    return True
                else:
                    logger.error("Failed to reload nginx")
                    self._restore_backup()
                    return False
            else:
                logger.error("Nginx config test failed")
                self._restore_backup()
                return False
                
        except Exception as e:
            logger.error(f"Failed to add agent route: {e}")
            return False
            
    def remove_agent_route(self, agent_name: str) -> bool:
        """
        Remove nginx routes for an agent.
        
        Args:
            agent_name: Agent name to remove
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.config_path.exists():
                logger.error(f"Nginx config not found at {self.config_path}")
                return False
                
            content = self.config_path.read_text()
            
            # Remove upstream block
            content = self._remove_block(
                content,
                f"upstream {agent_name} {{",
                "}"
            )
            
            # Remove OAuth route
            content = self._remove_block(
                content,
                f"location ~ ^/v1/auth/oauth/{agent_name}/",
                "    }"
            )
            
            # Remove API route
            content = self._remove_block(
                content,
                f"# {agent_name}",
                "    }"
            )
            
            # Backup and write new config
            self._backup_config()
            self.config_path.write_text(content)
            
            # Test and reload nginx
            if self._test_nginx_config():
                if self._reload_nginx():
                    logger.info(f"Successfully removed routes for agent {agent_name}")
                    return True
                else:
                    logger.error("Failed to reload nginx")
                    self._restore_backup()
                    return False
            else:
                logger.error("Nginx config test failed")
                self._restore_backup()
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove agent route: {e}")
            return False
            
    def get_configured_agents(self) -> Dict[str, int]:
        """
        Get list of agents configured in nginx.
        
        Returns:
            Dict mapping agent names to ports
        """
        agents = {}
        try:
            if not self.config_path.exists():
                return agents
                
            content = self.config_path.read_text()
            
            # Parse upstream blocks
            import re
            pattern = r'upstream\s+(\w+)\s*{\s*server\s+127\.0\.0\.1:(\d+);'
            matches = re.findall(pattern, content)
            
            for agent_name, port in matches:
                # Skip non-agent upstreams
                if agent_name in ['ciris_gui', 'ciris_manager']:
                    continue
                agents[agent_name] = int(port)
                
        except Exception as e:
            logger.error(f"Failed to parse nginx config: {e}")
            
        return agents
        
    def ensure_managed_sections(self) -> bool:
        """
        Ensure managed sections exist in nginx config.
        
        Returns:
            True if sections exist or were created
        """
        try:
            if not self.config_path.exists():
                logger.error(f"Nginx config not found at {self.config_path}")
                return False
                
            content = self.config_path.read_text()
            modified = False
            
            # Check for upstream section
            if self.UPSTREAM_START_MARKER not in content:
                # Add after initial upstreams
                insert_pos = content.find("upstream ciris_gui")
                if insert_pos > 0:
                    insert_pos = content.rfind("\n", 0, insert_pos)
                    content = (
                        content[:insert_pos] + "\n" +
                        self.UPSTREAM_START_MARKER + "\n" +
                        self.UPSTREAM_END_MARKER + "\n" +
                        content[insert_pos:]
                    )
                    modified = True
                    
            # Check for OAuth section
            if self.OAUTH_START_MARKER not in content:
                # Add before default /v1/ route
                insert_pos = content.find("# Default API endpoint")
                if insert_pos > 0:
                    content = (
                        content[:insert_pos] +
                        self.OAUTH_START_MARKER + "\n" +
                        self.OAUTH_END_MARKER + "\n\n    " +
                        content[insert_pos:]
                    )
                    modified = True
                    
            # Check for API routes section
            if self.API_START_MARKER not in content:
                # Add after CIRISManager routes
                insert_pos = content.find("# GUI (React app)")
                if insert_pos > 0:
                    content = (
                        content[:insert_pos] +
                        self.API_START_MARKER + "\n" +
                        self.API_END_MARKER + "\n\n    " +
                        content[insert_pos:]
                    )
                    modified = True
                    
            if modified:
                self._backup_config()
                self.config_path.write_text(content)
                return self._test_nginx_config()
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure managed sections: {e}")
            return False
            
    def _insert_block(self, content: str, block: str, 
                      start_marker: str, end_marker: str) -> str:
        """Insert a block between markers."""
        start_pos = content.find(start_marker)
        if start_pos < 0:
            raise ValueError(f"Marker {start_marker} not found")
            
        # Find end of start marker line
        start_pos = content.find("\n", start_pos) + 1
        
        # Insert block
        return content[:start_pos] + block + "\n" + content[start_pos:]
        
    def _remove_block(self, content: str, start_pattern: str, 
                      end_pattern: str) -> str:
        """Remove a block from content."""
        import re
        
        # Find start
        start_match = re.search(re.escape(start_pattern), content)
        if not start_match:
            return content
            
        # Find the line start
        line_start = content.rfind("\n", 0, start_match.start())
        if line_start < 0:
            line_start = 0
        else:
            line_start += 1
            
        # Find end pattern after start
        end_match = re.search(re.escape(end_pattern), content[start_match.start():])
        if not end_match:
            return content
            
        # Find end of line containing end pattern
        line_end = content.find("\n", start_match.start() + end_match.end())
        if line_end < 0:
            line_end = len(content)
        else:
            line_end += 1
            
        # Remove the block
        return content[:line_start] + content[line_end:]
        
    def _backup_config(self) -> None:
        """Create backup of current config."""
        backup_path = self.config_path.with_suffix(
            f".bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(self.config_path, backup_path)
        logger.info(f"Created backup at {backup_path}")
        
    def _restore_backup(self) -> None:
        """Restore most recent backup."""
        backup_dir = self.config_path.parent
        backups = sorted(backup_dir.glob(f"{self.config_path.name}.bak.*"))
        if backups:
            latest_backup = backups[-1]
            shutil.copy2(latest_backup, self.config_path)
            logger.info(f"Restored backup from {latest_backup}")
        else:
            logger.error("No backup found to restore")
            
    def _test_nginx_config(self) -> bool:
        """Test nginx configuration."""
        try:
            result = subprocess.run(
                ["nginx", "-t"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to test nginx config: {e}")
            return False
            
    def _reload_nginx(self) -> bool:
        """Reload nginx."""
        try:
            result = subprocess.run(
                self.reload_command.split(),
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to reload nginx: {e}")
            return False