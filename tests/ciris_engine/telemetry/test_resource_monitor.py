import asyncio
import pytest
from ciris_engine.telemetry.resource_monitor import ResourceMonitor, ResourceSignalBus
from ciris_engine.schemas.resource_schemas_v1 import ResourceBudget, ResourceAction


class DummyDB:
    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        class C:
            def cursor(self2):
                class Cur:
                    def execute(self3, q):
                        pass
                    def fetchone(self3):
                        return [0]
                return Cur()
        return C()

def patch_db(monkeypatch):
    monkeypatch.setattr("ciris_engine.telemetry.resource_monitor.get_db_connection", DummyDB())

def patch_psutil(monkeypatch):
    class P:
        def memory_info(self):
            class M: rss = 1024 * 1024
            return M()
        def cpu_percent(self, interval=0):
            return 10
    class D:
        free = 1024 * 1024
        used = 0

    class DummyPsutil:
        @staticmethod
        def Process():
            return P()

        @staticmethod
        def disk_usage(_):
            return D

    monkeypatch.setattr("ciris_engine.telemetry.resource_monitor.psutil", DummyPsutil)


@pytest.mark.asyncio
async def test_monitor_actions(monkeypatch):
    patch_db(monkeypatch)
    patch_psutil(monkeypatch)
    budget = ResourceBudget()
    budget.tokens_hour.warning = 1
    budget.tokens_hour.critical = 2
    bus = ResourceSignalBus()
    signals = []
    async def handler(sig, res):
        signals.append((sig, res))
    bus.register("defer", handler)
    monitor = ResourceMonitor(budget, "/tmp/db", bus)
    await monitor.record_tokens(3)
    await monitor._update_snapshot()
    await monitor._check_limits()
    assert ("defer", "tokens_hour") in signals

