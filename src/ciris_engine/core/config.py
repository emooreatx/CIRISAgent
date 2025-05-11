# src/ciris_engine/core/config.py
import os

# --- Database Configuration ---
SQLITE_DB_PATH = os.path.join(os.getcwd(), "data", "ciris_agent.db") # Assumes 'data' dir in project root

# --- LLM Configuration (can be expanded or loaded from .env) ---
# These might be better suited for the llm_client's own config or passed during instantiation,
# but placeholders here can guide its refactoring.
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini" # Example
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0 # Example timeout
DEFAULT_OPENAI_MAX_RETRIES = 2 # Example max retries
# API keys should be handled via environment variables, not hardcoded.

# --- Guardrail Thresholds (example, will be used by guardrails module later) ---
ENTROPY_THRESHOLD = 0.40
COHERENCE_THRESHOLD = 0.80

# --- Core Workflow Settings ---
DEFAULT_TASK_PRIORITY = 0
DEFAULT_THOUGHT_PRIORITY = 0

# Add other core configurations as they become clear
