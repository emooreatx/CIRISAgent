import asyncio
import pytest
from ciris_engine.telemetry.core import TelemetryService
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot

@pytest.mark.asyncio
async def test_buffer_size_enforced():
    service = TelemetryService(buffer_size=2)
    await service.record_metric("message_processed")
    await service.record_metric("message_processed")
    await service.record_metric("message_processed")
    assert len(service._history["message_processed"]) == 2

@pytest.mark.asyncio
async def test_snapshot_updates_counts():
    service = TelemetryService(buffer_size=10)
    for _ in range(5):
        await service.record_metric("message_processed")
    snapshot = SystemSnapshot()
    await service.update_system_snapshot(snapshot)
    assert snapshot.telemetry is not None
    assert snapshot.telemetry.messages_processed_24h == 5


@pytest.mark.asyncio
async def test_security_filter_integration():
    from ciris_engine.telemetry.security import SecurityFilter
    filt = SecurityFilter(bounds={"latency_ms": (0, 100)})
    service = TelemetryService(buffer_size=10, security_filter=filt)
    await service.record_metric("latency_ms", 200)
    assert "latency_ms" not in service._history
