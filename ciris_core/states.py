from enum import Enum

class AgentState(str, Enum):
    """High-level operational states for CIRIS agent."""
    WAKEUP = "wakeup"
    DREAM = "dream"
    PLAY = "play"
    SOLITUDE = "solitude"
    SHUTDOWN = "shutdown"
