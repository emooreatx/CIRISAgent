from __future__ import annotations

from typing import List, Optional, Dict, Any, Union

from ..models import (
    TelemetrySnapshot, SystemHealth, ServiceInfo, ProcessorState,
    MetricRecord, AdapterInfo
)
from ..transport import Transport

class SystemResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    # Telemetry Methods
    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        """Get complete system telemetry snapshot."""
        resp = await self._transport.request("GET", "/v1/system/telemetry")
        return TelemetrySnapshot(**resp.json())

    async def get_adapters_info(self) -> List[AdapterInfo]:
        """Get information about all registered adapters."""
        resp = await self._transport.request("GET", "/v1/system/adapters")
        adapters = []
        for adapter_data in resp.json():
            adapters.append(AdapterInfo(**adapter_data))
        return adapters

    async def get_services_info(self) -> List[ServiceInfo]:
        """Get information about all registered services."""
        resp = await self._transport.request("GET", "/v1/system/services")
        services = []
        for service_data in resp.json():
            services.append(ServiceInfo(**service_data))
        return services

    async def get_processor_state(self) -> ProcessorState:
        """Get current processor state information."""
        resp = await self._transport.request("GET", "/v1/system/processor/state")
        return ProcessorState(**resp.json())

    async def get_configuration_snapshot(self) -> Dict[str, Any]:
        """Get current system configuration snapshot."""
        resp = await self._transport.request("GET", "/v1/system/configuration")
        return resp.json()

    async def get_health_status(self) -> SystemHealth:
        """Get overall system health status."""
        resp = await self._transport.request("GET", "/v1/system/health")
        return SystemHealth(**resp.json())

    # Processor Control Methods (System endpoints)
    async def single_step(self) -> Dict[str, Any]:
        """Execute a single processing step via system endpoint."""
        resp = await self._transport.request("POST", "/v1/system/processor/step")
        return resp.json()

    async def pause_processing(self) -> Dict[str, Any]:
        """Pause the processor via system endpoint."""
        resp = await self._transport.request("POST", "/v1/system/processor/pause")
        return resp.json()

    async def resume_processing(self) -> Dict[str, Any]:
        """Resume the processor via system endpoint."""
        resp = await self._transport.request("POST", "/v1/system/processor/resume")
        return resp.json()

    async def get_processing_queue_status(self) -> Dict[str, Any]:
        """Get current processing queue status via system endpoint."""
        resp = await self._transport.request("GET", "/v1/system/processor/queue")
        return resp.json()

    # Metrics Methods
    async def record_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        tags: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Record a custom metric with optional tags."""
        payload = {
            "metric_name": metric_name,
            "value": value,
            "tags": tags or {}
        }
        resp = await self._transport.request("POST", "/v1/system/metrics", json=payload)
        return resp.json()

    async def get_metrics_history(
        self,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get historical data for a specific metric."""
        resp = await self._transport.request(
            "GET",
            f"/v1/system/metrics/{metric_name}/history",
            params={"hours": str(hours)}
        )
        return resp.json()
