from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime

from ..transport import Transport

class TelemetryResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    async def get_overview(self) -> Dict[str, Any]:
        """
        Get system metrics summary.

        Returns comprehensive overview combining telemetry, visibility, incidents, and resource usage.
        """
        resp = await self._transport.request("GET", "/v1/telemetry/overview")
        return resp.json()

    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get detailed metrics.

        Returns detailed metrics with trends and breakdowns by service.
        """
        resp = await self._transport.request("GET", "/v1/telemetry/metrics")
        return resp.json()

    async def get_traces(
        self,
        limit: int = 10,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get reasoning traces.

        Returns reasoning traces showing agent thought processes and decision-making.
        """
        params = {"limit": str(limit)}
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()

        resp = await self._transport.request("GET", "/v1/telemetry/traces", params=params)
        return resp.json()

    async def get_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get system logs.

        Returns system logs from all services with filtering capabilities.
        """
        params = {"limit": str(limit)}
        if start_time:
            params["start_time"] = start_time.isoformat()
        if end_time:
            params["end_time"] = end_time.isoformat()
        if level:
            params["level"] = level
        if service:
            params["service"] = service

        resp = await self._transport.request("GET", "/v1/telemetry/logs", params=params)
        return resp.json()

    async def query(
        self,
        query_type: str,
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Execute custom telemetry queries.

        Query types: metrics, traces, logs, incidents, insights
        Requires ADMIN role.
        """
        payload = {
            "query_type": query_type,
            "filters": filters or {},
            "limit": limit
        }

        if aggregations:
            payload["aggregations"] = aggregations
        if start_time:
            payload["start_time"] = start_time.isoformat()
        if end_time:
            payload["end_time"] = end_time.isoformat()

        resp = await self._transport.request("POST", "/v1/telemetry/query", json=payload)
        return resp.json()

    # Legacy compatibility methods (will be deprecated)
    async def get_observability_overview(self) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_overview() instead.
        Get unified observability overview.
        """
        return await self.get_overview()

    async def get_observability_metrics(self) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_metrics() instead.
        Get detailed system metrics.
        """
        return await self.get_metrics()

    async def get_observability_traces(
        self,
        limit: int = 10,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_traces() instead.
        Get reasoning traces.
        """
        return await self.get_traces(limit=limit, start_time=start_time, end_time=end_time)

    async def get_observability_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use get_logs() instead.
        Get system logs.
        """
        return await self.get_logs(
            start_time=start_time,
            end_time=end_time,
            level=level,
            service=service,
            limit=limit
        )

    async def query_observability(
        self,
        query_type: str,
        filters: Optional[Dict[str, Any]] = None,
        aggregations: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use query() instead.
        Execute custom observability queries.
        """
        return await self.query(
            query_type=query_type,
            filters=filters,
            aggregations=aggregations,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
