"""Unit tests for Resource Monitor Service."""

import pytest
import psutil
import tempfile
import os
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone
from typing import Optional

from ciris_engine.logic.services.infrastructure.resource_monitor import ResourceMonitorService, ResourceSignalBus
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.resources_core import (
    ResourceBudget, ResourceLimit, ResourceSnapshot, ResourceAction
)


@pytest.fixture
def time_service():
    """Create a time service for testing."""
    return TimeService()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


@pytest.fixture
def resource_budget():
    """Create a default resource budget for testing."""
    return ResourceBudget()


@pytest.fixture
def signal_bus():
    """Create a resource signal bus for testing."""
    return ResourceSignalBus()


@pytest.fixture
def resource_monitor(resource_budget, temp_db, time_service, signal_bus):
    """Create a resource monitor service for testing."""
    return ResourceMonitorService(
        budget=resource_budget,
        db_path=temp_db,
        time_service=time_service,
        signal_bus=signal_bus
    )


@pytest.mark.asyncio
async def test_resource_monitor_lifecycle(resource_monitor):
    """Test ResourceMonitorService start/stop lifecycle."""
    # Start
    await resource_monitor.start()
    assert resource_monitor._monitoring is True

    # Give it a moment to start monitoring
    await asyncio.sleep(0.1)

    # Stop
    await resource_monitor.stop()
    assert resource_monitor._monitoring is False


def test_resource_monitor_get_snapshot(resource_monitor):
    """Test getting current resource snapshot."""
    snapshot = resource_monitor.snapshot

    assert isinstance(snapshot, ResourceSnapshot)
    assert snapshot.memory_mb >= 0
    assert 0 <= snapshot.memory_percent <= 100
    assert 0 <= snapshot.cpu_percent <= 100
    assert snapshot.cpu_average_1m >= 0
    assert snapshot.tokens_used_hour >= 0
    assert snapshot.tokens_used_day >= 0
    assert snapshot.disk_used_mb >= 0
    assert snapshot.disk_free_mb >= 0
    assert snapshot.thoughts_active >= 0
    assert isinstance(snapshot.healthy, bool)
    assert isinstance(snapshot.warnings, list)
    assert isinstance(snapshot.critical, list)


@pytest.mark.asyncio
async def test_resource_monitor_check_limits(resource_monitor):
    """Test resource limit checking."""
    # Modify budget to have low limits for testing
    resource_monitor.budget.memory_mb = ResourceLimit(
        limit=100,
        warning=50,
        critical=80,
        action=ResourceAction.WARN
    )
    resource_monitor.budget.cpu_percent = ResourceLimit(
        limit=80,
        warning=60,
        critical=75,
        action=ResourceAction.THROTTLE
    )

    # Set current values that exceed limits
    resource_monitor.snapshot.memory_mb = 85  # Exceeds critical
    resource_monitor.snapshot.cpu_average_1m = 65  # Exceeds warning

    # Check limits
    await resource_monitor._check_limits()

    # Verify warnings/critical were set
    assert len(resource_monitor.snapshot.critical) >= 1
    assert any("memory_mb" in c for c in resource_monitor.snapshot.critical)
    assert len(resource_monitor.snapshot.warnings) >= 1
    assert any("cpu_percent" in w for w in resource_monitor.snapshot.warnings)
    assert resource_monitor.snapshot.healthy is False




def test_resource_monitor_status(resource_monitor):
    """Test ResourceMonitorService.get_status() returns correct status."""
    status = resource_monitor.get_status()
    assert isinstance(status, ServiceStatus)
    assert status.service_name == "ResourceMonitorService"
    assert status.service_type == "infrastructure_service"
    assert status.is_healthy is True
    assert "memory_mb" in status.metrics
    assert "cpu_percent" in status.metrics
    assert "tokens_used_hour" in status.metrics
    assert "thoughts_active" in status.metrics
    assert "warnings" in status.metrics
    assert "critical" in status.metrics


@pytest.mark.asyncio
async def test_resource_monitor_continuous_monitoring(resource_monitor):
    """Test continuous monitoring loop."""
    # Start monitoring
    await resource_monitor.start()

    # Capture initial snapshot values
    initial_healthy = resource_monitor.snapshot.healthy

    # Let it run briefly
    await asyncio.sleep(0.2)

    # Stop monitoring
    await resource_monitor.stop()

    # Verify monitoring ran
    assert resource_monitor.snapshot is not None
    assert isinstance(resource_monitor.snapshot.healthy, bool)


@pytest.mark.asyncio
async def test_resource_monitor_record_tokens(resource_monitor):
    """Test token recording."""
    # Record some tokens
    await resource_monitor.record_tokens(100)
    await resource_monitor.record_tokens(200)
    await resource_monitor.record_tokens(300)

    # Update snapshot to calculate totals
    await resource_monitor._update_snapshot()

    # Check token counts
    assert resource_monitor.snapshot.tokens_used_hour == 600
    assert resource_monitor.snapshot.tokens_used_day == 600


@pytest.mark.asyncio
async def test_resource_monitor_check_available(resource_monitor):
    """Test checking resource availability."""
    # Set current usage
    resource_monitor.snapshot.memory_mb = 40
    resource_monitor.snapshot.tokens_used_hour = 1000
    resource_monitor.snapshot.thoughts_active = 10

    # Check availability - should have room
    assert await resource_monitor.check_available("memory_mb", 5) is True
    assert await resource_monitor.check_available("tokens_hour", 100) is True
    assert await resource_monitor.check_available("thoughts_active", 5) is True

    # Check with amounts that would exceed warning threshold
    assert await resource_monitor.check_available("memory_mb", 200) is True  # 40 + 200 = 240 < 3072 warning
    assert await resource_monitor.check_available("tokens_hour", 8000) is False  # 1000 + 8000 = 9000 > 8000 warning
    assert await resource_monitor.check_available("thoughts_active", 35) is False  # 10 + 35 = 45 > 40 warning


@pytest.mark.asyncio
async def test_resource_monitor_signal_bus(resource_monitor, signal_bus):
    """Test signal bus integration."""
    # Track emitted signals
    emitted_signals = []

    async def signal_handler(signal: str, resource: str):
        emitted_signals.append((signal, resource))

    # Register handlers
    signal_bus.register("throttle", signal_handler)
    signal_bus.register("defer", signal_handler)
    signal_bus.register("reject", signal_handler)

    # Set budget with different actions
    resource_monitor.budget.cpu_percent.action = ResourceAction.THROTTLE
    resource_monitor.budget.memory_mb.action = ResourceAction.DEFER
    resource_monitor.budget.tokens_hour.action = ResourceAction.REJECT

    # Trigger critical limits
    resource_monitor.snapshot.cpu_average_1m = 76  # Exceeds critical (75)
    resource_monitor.snapshot.memory_mb = 3841  # Exceeds critical (3840)
    resource_monitor.snapshot.tokens_used_hour = 9501  # Exceeds critical (9500)

    # Check limits
    await resource_monitor._check_limits()

    # Verify signals were emitted
    assert len(emitted_signals) >= 3
    assert ("throttle", "cpu_percent") in emitted_signals
    assert ("defer", "memory_mb") in emitted_signals
    assert ("reject", "tokens_hour") in emitted_signals


@pytest.mark.asyncio
async def test_resource_monitor_update_snapshot(resource_monitor):
    """Test snapshot updating."""
    # Update the snapshot
    await resource_monitor._update_snapshot()

    # Verify snapshot was populated
    snapshot = resource_monitor.snapshot
    assert snapshot.memory_mb >= 0
    assert snapshot.cpu_percent >= 0
    assert snapshot.cpu_average_1m >= 0
    assert snapshot.disk_used_mb >= 0
    assert snapshot.disk_free_mb >= 0


@pytest.mark.asyncio
async def test_resource_monitor_is_healthy(resource_monitor):
    """Test health check."""
    # Initially should be healthy
    assert await resource_monitor.is_healthy() is True

    # Add critical issues
    resource_monitor.snapshot.critical.append("memory_mb: 250/256")
    resource_monitor.snapshot.healthy = False

    # Should now be unhealthy
    assert await resource_monitor.is_healthy() is False


@pytest.mark.asyncio
async def test_resource_monitor_cooldown(resource_monitor, signal_bus):
    """Test action cooldown functionality."""
    # Track emitted signals
    emitted_signals = []

    async def signal_handler(signal: str, resource: str):
        emitted_signals.append((signal, resource, resource_monitor.time_service.now()))

    signal_bus.register("defer", signal_handler)

    # Set short cooldown for testing
    resource_monitor.budget.memory_mb.cooldown_seconds = 1
    resource_monitor.budget.memory_mb.action = ResourceAction.DEFER

    # Exceed critical threshold multiple times quickly
    resource_monitor.snapshot.memory_mb = 3841  # Exceeds critical (3840)

    # First check should emit signal
    await resource_monitor._check_limits()
    initial_count = len(emitted_signals)
    assert initial_count == 1  # Should have one signal

    # Immediate second check should not emit due to cooldown
    await resource_monitor._check_limits()
    assert len(emitted_signals) == initial_count

    # Wait for cooldown
    await asyncio.sleep(1.1)

    # Now should emit again
    await resource_monitor._check_limits()
    assert len(emitted_signals) > initial_count


def test_resource_monitor_get_capabilities(resource_monitor):
    """Test get_capabilities method."""
    # ResourceMonitorService should implement get_capabilities
    caps = resource_monitor.get_capabilities()
    assert isinstance(caps, ServiceCapabilities)
    assert caps.service_name == "ResourceMonitorService"
    assert caps.version == "1.0.0"
    assert "resource_monitoring" in caps.actions
    assert "cpu_tracking" in caps.actions
    assert "memory_tracking" in caps.actions
    assert "token_rate_limiting" in caps.actions
    assert "TimeService" in caps.dependencies
