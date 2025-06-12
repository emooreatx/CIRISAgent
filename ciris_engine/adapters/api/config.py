"""Configuration schema for API adapter."""

from pydantic import BaseModel, Field
from typing import Optional


class APIAdapterConfig(BaseModel):
    """Configuration for the API adapter."""
    
    # Server configuration
    host: str = Field(default="0.0.0.0", description="Host to bind API server to")
    port: int = Field(default=8080, description="Port to bind API server to")
    
    # Request handling
    max_request_size: int = Field(default=1024 * 1024, description="Maximum request size in bytes")
    timeout_seconds: float = Field(default=30.0, description="Request timeout in seconds")
    
    # CORS configuration
    enable_cors: bool = Field(default=True, description="Enable CORS for web browsers")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="Allowed CORS origins")
    
    # Rate limiting
    enable_rate_limiting: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(default=60, description="Requests per minute per IP")
    
    # Security
    require_auth: bool = Field(default=False, description="Require authentication for API access")
    api_key: Optional[str] = Field(default=None, description="API key for authentication")
    
    # Channel configuration
    default_channel_id: Optional[str] = Field(default=None, description="Default channel ID for API messages")
    
    def get_channel_id(self, host: str, port: int) -> str:
        """Get the channel ID for this API instance."""
        if self.default_channel_id:
            return self.default_channel_id
        return f"{host}:{port}"

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var
        
        env_host = get_env_var("CIRIS_API_HOST")
        if env_host:
            self.host = env_host
            
        env_port = get_env_var("CIRIS_API_PORT")
        if env_port:
            self.port = int(env_port)
            
        env_api_key = get_env_var("CIRIS_API_KEY")
        if env_api_key:
            self.api_key = env_api_key
            self.require_auth = True