import pytest
import pytest_asyncio
from typing import Any
import sys

from ciris_engine.logic.registries.base import ServiceRegistry
from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime


@pytest_asyncio.fixture
async def service_registry() -> Any:
    """Provide a configured service registry with mock services."""
    registry = ServiceRegistry()
    # Register mock services here when needed
    return registry


@pytest_asyncio.fixture
async def runtime():
    """Provide a CIRISRuntime instance with proper initialization."""
    runtime = CIRISRuntime(adapter_types=["cli"])
    # The runtime will initialize its own service registry during initialization
    # No need to set it externally - this violates encapsulation
    return runtime


@pytest.fixture(autouse=True)
def ensure_pydantic_models_rebuilt():
    """Ensure Pydantic models are properly rebuilt before each test.

    This prevents issues with forward references when tests run in different orders.
    """
    # Import and rebuild models
    try:
        # Models are now automatically rebuilt - no manual rebuild needed
        pass
    except ImportError:
        pass  # Schema module may not be imported yet

    yield

    # No cleanup needed - models will be rebuilt for next test
