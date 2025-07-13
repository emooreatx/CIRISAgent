"""Configuration schema for CLI adapter."""

from pydantic import BaseModel, Field
from typing import Optional
import os
import uuid

class CLIAdapterConfig(BaseModel):
    """Configuration for the CLI adapter."""

    interactive: bool = Field(default=True, description="Enable interactive CLI input")

    prompt_prefix: str = Field(default="CIRIS> ", description="CLI prompt prefix")
    enable_colors: bool = Field(default=True, description="Enable colored output")
    max_history_entries: int = Field(default=1000, description="Maximum command history entries")

    input_timeout_seconds: float = Field(default=30.0, description="Timeout for user input in seconds")
    multiline_mode: bool = Field(default=False, description="Enable multiline input mode")

    max_output_lines: int = Field(default=100, description="Maximum lines to display per response")
    word_wrap: bool = Field(default=True, description="Enable word wrapping for long lines")

    default_channel_id: Optional[str] = Field(
        default_factory=lambda: f"cli_{os.getpid()}_{uuid.uuid4().hex[:8]}", 
        description="Default channel ID for CLI messages"
    )

    enable_cli_tools: bool = Field(default=True, description="Enable CLI-specific tools")

    def get_home_channel_id(self) -> str:
        """Get the home channel ID for this CLI adapter instance."""
        if self.default_channel_id:
            return self.default_channel_id

        # Generate unique channel ID for this connection
        try:
            import uuid
            import os
            return f"cli_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        except Exception:
            return "cli_default"

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.logic.config.env_utils import get_env_var

        env_interactive = get_env_var("CIRIS_CLI_INTERACTIVE")
        if env_interactive is not None:
            self.interactive = env_interactive.lower() in ("true", "1", "yes", "on")

        env_colors = get_env_var("CIRIS_CLI_COLORS")
        if env_colors is not None:
            self.enable_colors = env_colors.lower() in ("true", "1", "yes", "on")

        env_channel = get_env_var("CIRIS_CLI_CHANNEL_ID")
        if env_channel:
            self.default_channel_id = env_channel

        env_prompt = get_env_var("CIRIS_CLI_PROMPT")
        if env_prompt:
            self.prompt_prefix = env_prompt

