import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WA = os.getenv("WA_DISCORD_USER", "somecomputerguy")
WA_USER_ID = os.getenv("WA_USER_ID")

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


