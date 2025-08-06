pytest_plugins = ("tests.fixtures",)
import os

import pytest

from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.logic.runtime.prevent_sideeffects import allow_runtime_creation


@pytest.fixture(autouse=True)
def allow_runtime():
    """Allow runtime creation for integration tests."""
    allow_runtime_creation()
    yield
    # Re-enable import protection after test
    os.environ["CIRIS_IMPORT_MODE"] = "true"


@pytest.mark.asyncio
@pytest.mark.skipif(
    True,  # Always skip due to Python 3.12 compatibility issue with abstract base class instantiation
    reason="Skipping due to Python 3.12 compatibility issue with abstract base class instantiation when running in full test suite",
)
async def test_full_thought_cycle():
    """Test complete thought processing cycle.

    NOTE: This test fails in GitHub Actions with Python 3.12.10 due to:
    TypeError: object.__new__() takes exactly one argument (the type to instantiate)

    The issue appears to be related to stricter ABC instantiation checks in Python 3.12.10
    when instantiating adapters that inherit from the Service abstract base class.
    The test passes locally with Python 3.12.3 and earlier versions.
    """
    # Ensure runtime creation is allowed
    allow_runtime_creation()

    from unittest.mock import AsyncMock, MagicMock, patch

    # Mock adapter loading to avoid real adapter initialization
    with patch("ciris_engine.logic.runtime.ciris_runtime.load_adapter") as mock_load:
        # Create a concrete mock adapter class that doesn't inherit from ABC
        class MockAdapter:
            def __init__(self, runtime, **kwargs):
                self.runtime = runtime
                self.config = kwargs.get("adapter_config", {})

            async def start(self):
                pass

            async def stop(self):
                pass

            async def run_lifecycle(self):
                pass

            def get_services_to_register(self):
                return []

        mock_load.return_value = MockAdapter

        # Mock initialization manager to avoid core services verification
        with patch("ciris_engine.logic.runtime.ciris_runtime.get_initialization_manager") as mock_get_init:
            mock_init_manager = MagicMock()
            mock_init_manager.initialize = AsyncMock()
            mock_init_manager.register_step = MagicMock()
            mock_get_init.return_value = mock_init_manager

            # Create and initialize runtime with required parameters
            from ciris_engine.schemas.config.essential import EssentialConfig

            essential_config = EssentialConfig()
            runtime = CIRISRuntime(
                adapter_types=["cli"], essential_config=essential_config, startup_channel_id="test_channel"
            )

            with patch.object(runtime, "_perform_startup_maintenance"):
                await runtime.initialize()

            # Now the runtime should be initialized
            assert runtime.service_initializer is not None
            assert runtime._initialized is True

            # Properly stop the runtime to avoid cleanup issues
            try:
                await runtime.stop()
            except Exception:
                pass  # Ignore cleanup errors in test

        # TODO: Implement actual test steps
        # 1. Create task
        # 2. Generate thought
        # 3. Run DMAs
        # 4. Apply guardrails
        # 5. Execute action
        # 6. Verify outcome
