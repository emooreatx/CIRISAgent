"""Visibility resource - windows into agent reasoning and state."""
from typing import Any, Dict, List, Optional
from ..transport import Transport


class VisibilityResource:
    """Resource for visibility endpoints."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def thoughts(self, limit: int = 10) -> Dict[str, Any]:
        """Get current active thoughts.

        Args:
            limit: Maximum number of thoughts to return

        Returns:
            Current thoughts and metadata
        """
        params = {"limit": limit}
        return await self._transport.request(
            "GET",
            "/v1/visibility/thoughts",
            params=params
        )

    async def tasks(self) -> Dict[str, Any]:
        """Get active tasks.

        Returns:
            Active tasks the agent is working on
        """
        return await self._transport.request("GET", "/v1/visibility/tasks")

    async def system_snapshot(self) -> Dict[str, Any]:
        """Get current system snapshot.

        Returns:
            The agent's awareness of its own state
        """
        return await self._transport.request("GET", "/v1/visibility/system-snapshot")

    async def decisions(self, limit: int = 20) -> Dict[str, Any]:
        """Get recent decisions made by DMAs.

        Args:
            limit: Maximum number of decisions to return

        Returns:
            Recent decisions with reasoning
        """
        params = {"limit": limit}
        return await self._transport.request(
            "GET",
            "/v1/visibility/decisions",
            params=params
        )

    async def correlations(
        self,
        limit: int = 50,
        correlation_type: Optional[str] = None,
        service: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get service correlations.

        Args:
            limit: Maximum number of correlations
            correlation_type: Filter by type
            service: Filter by service name

        Returns:
            Service interaction correlations
        """
        params = {"limit": limit}
        if correlation_type:
            params["type"] = correlation_type
        if service:
            params["service"] = service

        return await self._transport.request(
            "GET",
            "/v1/visibility/correlations",
            params=params
        )

    async def task_details(self, task_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific task.

        Args:
            task_id: Task ID to get details for

        Returns:
            Task details including associated thoughts
        """
        return await self._transport.request(
            "GET",
            f"/v1/visibility/tasks/{task_id}"
        )

    async def thought_details(self, thought_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific thought.

        Args:
            thought_id: Thought ID to get details for

        Returns:
            Thought details including processing history
        """
        return await self._transport.request(
            "GET",
            f"/v1/visibility/thoughts/{thought_id}"
        )
