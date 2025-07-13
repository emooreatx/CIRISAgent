"""Task Scheduler Service Protocol."""

from typing import Protocol, Any, List, Callable
from abc import abstractmethod
from datetime import datetime

from ...runtime.base import ServiceProtocol
from ciris_engine.schemas.runtime.extended import ScheduledTaskInfo

class TaskSchedulerServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for task scheduler service."""

    @abstractmethod
    async def schedule_task(
        self,
        task_id: str,
        _: datetime,
        handler: Callable,
        **kwargs: Any
    ) -> bool:
        """Schedule a task to run at a specific time."""
        ...

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        ...

    @abstractmethod
    async def get_scheduled_tasks(self) -> List[ScheduledTaskInfo]:
        """Get all scheduled tasks."""
        ...
