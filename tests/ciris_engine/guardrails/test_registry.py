import pytest
from unittest.mock import AsyncMock

from ciris_engine.guardrails.registry import GuardrailRegistry, GuardrailInterface

class DummyGuardrail:
    async def check(self, action, context):
        return None

def test_registry_orders_by_priority_and_enable():
    registry = GuardrailRegistry()
    g1 = DummyGuardrail()
    g2 = DummyGuardrail()
    registry.register_guardrail("g1", g1, priority=10)
    registry.register_guardrail("g2", g2, priority=5)

    names = [e.name for e in registry.get_guardrails()]
    assert names == ["g2", "g1"]

    registry.set_enabled("g2", False)
    names_after = [e.name for e in registry.get_guardrails()]
    assert names_after == ["g1"]

