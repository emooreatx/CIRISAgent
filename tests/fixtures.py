import pytest

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.fixture
async def service_registry():
    """Provide a configured service registry with mock services."""
    registry = ServiceRegistry()
    # Register mock services here when needed
    return registry


@pytest.fixture
async def runtime(service_registry):
    """Provide a CIRISRuntime instance using the service registry."""
    runtime = CIRISRuntime(modes=["cli"], profile_name="test")
    runtime.service_registry = service_registry
    return runtime
