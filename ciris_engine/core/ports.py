from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict
import logging

logger = logging.getLogger(__name__)


class EventSource(ABC):
    """Asynchronous source of events driving the agent."""

    @abstractmethod
    async def start(self) -> None:
        """Begin producing events."""
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        """Stop producing events and clean up."""
        raise NotImplementedError

    def __aiter__(self) -> AsyncIterator[Dict[str, Any]]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Dict[str, Any]]:
        while False:
            yield {}


class ActionSink(ABC):
    """Consumer of agent actions."""

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_message(self, channel_id: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def run_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        raise NotImplementedError
