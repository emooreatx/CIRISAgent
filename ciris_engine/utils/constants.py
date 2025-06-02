import os
import logging
from pathlib import Path
from ciris_engine.config.env_utils import get_env_var

logger = logging.getLogger(__name__)

DEFAULT_WA = get_env_var("WA_DISCORD_USER", "somecomputerguy")
WA_USER_ID = get_env_var("WA_USER_ID")

# Common service channel/environment variables
DISCORD_CHANNEL_ID = get_env_var("DISCORD_CHANNEL_ID")
DISCORD_DEFERRAL_CHANNEL_ID = get_env_var("DISCORD_DEFERRAL_CHANNEL_ID")
API_CHANNEL_ID = get_env_var("API_CHANNEL_ID")
API_DEFERRAL_CHANNEL_ID = get_env_var("API_DEFERRAL_CHANNEL_ID")
WA_API_USER = get_env_var("WA_API_USER", DEFAULT_WA)

# Load the CIRIS Covenant text for inclusion in prompts
_COVENANT_PATH = Path(__file__).resolve().parents[2] / "covenant_1.0b.txt"
try:
    with open(_COVENANT_PATH, "r", encoding="utf-8") as f:
        COVENANT_TEXT = f.read()
except Exception as exc:  # noqa: BLE001
    logger.warning("Could not load covenant text from %s: %s", _COVENANT_PATH, exc)
    COVENANT_TEXT = ""

# Flag indicating that a memory meta-thought should be generated for the
# originating context. It is toggled by the ActionDispatcher when
# external actions occur and cleared once a meta-thought has been enqueued.
NEED_MEMORY_METATHOUGHT = "need_memory_metathought"

# Overview of how the engine handles actions. Included in prompts for clarity.
ENGINE_OVERVIEW_TEMPLATE = (
    "ENGINE OVERVIEW: The CIRIS Engine processes a task through a sequence of "
    "Thoughts. Each handler action except TASK_COMPLETE enqueues a new Thought "
    "for further processing. Selecting TASK_COMPLETE marks the task closed and "
    "no new Thought is generated."
)

# Depth and ponder safeguards
MAX_THOUGHT_DEPTH = 7
MAX_PONDER_COUNT = 7

# Processing rounds control
DEFAULT_NUM_ROUNDS = None  # None means infinite rounds (no limit)


