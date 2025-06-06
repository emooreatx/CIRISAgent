import pytest

from ciris_engine.registries.base import ServiceRegistry, Priority, SelectionStrategy

class HealthyService:
    async def is_healthy(self) -> bool:
        return True

class UnhealthyService:
    async def is_healthy(self) -> bool:
        return False

@pytest.mark.asyncio
async def test_round_robin_selection():
    reg = ServiceRegistry()
    s1 = HealthyService()
    s2 = HealthyService()
    reg.register(
        handler="H",
        service_type="comm",
        provider=s1,
        priority=Priority.NORMAL,
        priority_group=0,
        strategy=SelectionStrategy.ROUND_ROBIN,
    )
    reg.register(
        handler="H",
        service_type="comm",
        provider=s2,
        priority=Priority.NORMAL,
        priority_group=0,
        strategy=SelectionStrategy.ROUND_ROBIN,
    )
    first = await reg.get_service("H", "comm")
    second = await reg.get_service("H", "comm")
    assert first is s1
    assert second is s2

@pytest.mark.asyncio
async def test_priority_group_fallback():
    reg = ServiceRegistry()
    s1 = UnhealthyService()
    s2 = HealthyService()
    reg.register(
        handler="H",
        service_type="comm",
        provider=s1,
        priority=Priority.NORMAL,
        priority_group=0,
    )
    reg.register(
        handler="H",
        service_type="comm",
        provider=s2,
        priority=Priority.NORMAL,
        priority_group=1,
    )
    service = await reg.get_service("H", "comm")
    assert service is s2
