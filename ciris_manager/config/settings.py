"""
Configuration settings for CIRISManager.
"""
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class WatchdogConfig(BaseModel):
    """Watchdog configuration."""
    check_interval: int = Field(default=30, description="Seconds between checks")
    crash_threshold: int = Field(default=3, description="Number of crashes to trigger intervention")
    crash_window: int = Field(default=300, description="Time window in seconds to count crashes")


class UpdateConfig(BaseModel):
    """Update checking configuration."""
    check_interval: int = Field(default=300, description="Seconds between update checks")
    auto_notify: bool = Field(default=True, description="Automatically notify agents of updates")


class ContainerConfig(BaseModel):
    """Container management configuration."""
    interval: int = Field(default=60, description="Seconds between docker-compose up -d runs")
    pull_images: bool = Field(default=True, description="Pull latest images before starting")


class DockerConfig(BaseModel):
    """Docker configuration."""
    compose_file: str = Field(
        default="/home/ciris/CIRISAgent/deployment/docker-compose.yml",
        description="Path to docker-compose.yml"
    )


class ManagerConfig(BaseModel):
    """Manager API configuration."""
    port: int = Field(default=9999, description="API port")
    socket: Optional[str] = Field(
        default="/var/run/ciris-manager.sock",
        description="Unix socket path"
    )
    host: str = Field(default="127.0.0.1", description="API host")


class CIRISManagerConfig(BaseModel):
    """Complete CIRISManager configuration."""
    manager: ManagerConfig = Field(default_factory=ManagerConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    watchdog: WatchdogConfig = Field(default_factory=WatchdogConfig)
    updates: UpdateConfig = Field(default_factory=UpdateConfig)
    container_management: ContainerConfig = Field(default_factory=ContainerConfig)
    
    @classmethod
    def from_file(cls, path: str) -> "CIRISManagerConfig":
        """Load configuration from YAML file."""
        import yaml
        
        config_path = Path(path)
        if not config_path.exists():
            # Return default config
            return cls()
            
        with open(config_path) as f:
            data = yaml.safe_load(f)
            
        return cls(**data)
        
    def save(self, path: str):
        """Save configuration to YAML file."""
        import yaml
        
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)