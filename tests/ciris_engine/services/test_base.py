import pytest
from ciris_engine.services.base import Service
import asyncio

class DummyService(Service):
    async def start(self):
        self.started = True
    async def stop(self):
        self.stopped = True

def test_service_repr():
    s = DummyService()
    assert repr(s) == f"<{s.service_name}>"

@pytest.mark.asyncio
async def test_service_start_stop():
    s = DummyService()
    await s.start()
    await s.stop()
    assert hasattr(s, "started")
    assert hasattr(s, "stopped")
