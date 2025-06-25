"""Lifecycle service protocols."""

from .time import TimeServiceProtocol
from .shutdown import ShutdownServiceProtocol
from .initialization import InitializationServiceProtocol
from .scheduler import TaskSchedulerServiceProtocol

__all__ = [
    "TimeServiceProtocol",
    "ShutdownServiceProtocol",
    "InitializationServiceProtocol",
    "TaskSchedulerServiceProtocol",
]