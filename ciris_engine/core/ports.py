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


class DeferralSink(ABC):
    """Specialized sink for sending deferral packages and handling WA corrections."""

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_deferral(
        self,
        task_id: str,
        thought_id: str,
        reason: str,
        package: Dict[str, Any],
    ) -> None:
        """Send a deferral report to the WA channel."""
        raise NotImplementedError

    async def process_possible_correction(self, msg: Any, raw_message: Any) -> bool:
        """Handle WA correction replies if applicable. Return True if handled."""
        return False
