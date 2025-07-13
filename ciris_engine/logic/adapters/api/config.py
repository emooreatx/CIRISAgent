"""Configuration schema for API adapter."""

from pydantic import BaseModel, Field
from ciris_engine.constants import DEFAULT_API_HOST, DEFAULT_API_PORT

class APIAdapterConfig(BaseModel):
    """Configuration for the API adapter."""
    
    host: str = Field(default=DEFAULT_API_HOST, description="API server host")
    port: int = Field(default=DEFAULT_API_PORT, description="API server port")
    
    cors_enabled: bool = Field(default=True, description="Enable CORS support")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="Allowed CORS origins")
    
    max_request_size: int = Field(default=1024 * 1024, description="Maximum request size in bytes")
    request_timeout: float = Field(default=30.0, description="Request timeout in seconds")
    
    enable_swagger: bool = Field(default=True, description="Enable Swagger/OpenAPI documentation")
    enable_redoc: bool = Field(default=True, description="Enable ReDoc documentation")
    
    rate_limit_enabled: bool = Field(default=False, description="Enable rate limiting")
    rate_limit_per_minute: int = Field(default=60, description="Requests per minute limit")
    
    auth_enabled: bool = Field(default=True, description="Enable authentication")
    
    # Timeout configuration
    interaction_timeout: float = Field(default=55.0, description="Timeout for agent interactions in seconds")
    
    def get_home_channel_id(self, host: str, port: int) -> str:
        """Get the home channel ID for this API adapter instance."""
        return f"api_{host}_{port}"
    
    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.logic.config.env_utils import get_env_var
        
        env_host = get_env_var("CIRIS_API_HOST")
        if env_host:
            self.host = env_host
            
        env_port = get_env_var("CIRIS_API_PORT")
        if env_port:
            try:
                self.port = int(env_port)
            except ValueError:
                pass
                
        env_cors = get_env_var("CIRIS_API_CORS_ENABLED")
        if env_cors is not None:
            self.cors_enabled = env_cors.lower() in ("true", "1", "yes", "on")
            
        env_auth = get_env_var("CIRIS_API_AUTH_ENABLED")
        if env_auth is not None:
            self.auth_enabled = env_auth.lower() in ("true", "1", "yes", "on")
            
        env_timeout = get_env_var("CIRIS_API_INTERACTION_TIMEOUT")
        if env_timeout:
            try:
                self.interaction_timeout = float(env_timeout)
            except ValueError:
                pass
