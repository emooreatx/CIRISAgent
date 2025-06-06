import asyncio
import pytest

from ciris_engine.telemetry.security import SecurityFilter

@pytest.mark.asyncio
async def test_pii_detection_blocks_metric():
    f = SecurityFilter()
    result = f.sanitize("latency_ms", "john@example.com")
    assert result is None

@pytest.mark.asyncio
async def test_error_message_sanitized():
    f = SecurityFilter()
    name, value = f.sanitize("db.error", "failed at /tmp/test.txt")
    assert "/tmp" not in value

@pytest.mark.asyncio
async def test_bounds_validation():
    f = SecurityFilter(bounds={"latency_ms": (0, 100)})
    result = f.sanitize("latency_ms", 200)
    assert result is None

@pytest.mark.asyncio
async def test_rate_limiting():
    f = SecurityFilter(rate_limits={"message": (2, 1)})
    assert f.sanitize("message", 1) is not None
    assert f.sanitize("message", 1) is not None
    assert f.sanitize("message", 1) is None
