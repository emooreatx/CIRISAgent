import pytest

from ciris_engine.services.multi_service_transaction_orchestrator import (
    MultiServiceTransactionOrchestrator,
)
from ciris_engine.schemas.service_actions_v1 import SendMessageAction


class DummySink:
    def __init__(self):
        self.actions = []

    async def enqueue_action(self, action):
        self.actions.append(action)
        return True


class FailingSink(DummySink):
    async def enqueue_action(self, action):
        if getattr(action, "content", "") == "fail":
            raise RuntimeError("fail")
        return await super().enqueue_action(action)


class DummyRegistry:
    def get_provider_info(self):
        return {"dummy": True}


@pytest.mark.asyncio
async def test_transaction_success():
    sink = DummySink()
    reg = DummyRegistry()
    orch = MultiServiceTransactionOrchestrator(reg, sink)
    await orch.start()
    actions = [
        SendMessageAction("test", {}, "chan", "hi"),
        SendMessageAction("test", {}, "chan", "bye"),
    ]
    await orch.orchestrate("tx1", actions)
    status = await orch.get_status("tx1")
    await orch.stop()
    assert status["status"] == "complete"
    assert len(sink.actions) == 2


@pytest.mark.asyncio
async def test_transaction_failure():
    sink = FailingSink()
    reg = DummyRegistry()
    orch = MultiServiceTransactionOrchestrator(reg, sink)
    await orch.start()
    actions = [SendMessageAction("test", {}, "chan", "fail")]
    await orch.orchestrate("tx2", actions)
    status = await orch.get_status("tx2")
    await orch.stop()
    assert status["status"] == "failed"


def test_service_health():
    sink = DummySink()
    reg = DummyRegistry()
    orch = MultiServiceTransactionOrchestrator(reg, sink)
    info = orch.get_service_health()
    assert info == {"dummy": True}
