"""
CIRISAgent processor module.
Provides state-aware task and thought processing using v1 schemas.
"""

from .base_processor import BaseProcessor
from .wakeup_processor import WakeupProcessor
from .work_processor import WorkProcessor
from .play_processor import PlayProcessor
from .dream_processor import DreamProcessor
from .solitude_processor import SolitudeProcessor
from .main_processor import AgentProcessor
from .state_manager import StateManager, StateTransition
from .task_manager import TaskManager
from .thought_manager import ThoughtManager

__all__ = [
    "AgentProcessor",
    "BaseProcessor",
    "WakeupProcessor",
    "WorkProcessor",
    "PlayProcessor",
    "DreamProcessor",
    "SolitudeProcessor",
    "StateManager",
    "StateTransition", 
    "TaskManager",
    "ThoughtManager",
]