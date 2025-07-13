"""Central constants for CIRIS."""
from pathlib import Path

# Agent defaults
DEFAULT_WA = "CIRIS"
DEFAULT_TEMPLATE = "default"
DEFAULT_TEMPLATE_PATH = Path("ciris_templates")

# Model defaults  
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"

# Prompt defaults
DEFAULT_PROMPT_TEMPLATE = "default_prompt"

# System defaults
DEFAULT_NUM_ROUNDS = 10

# API defaults
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8080