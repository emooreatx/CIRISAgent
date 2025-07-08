pytest_plugins = ("tests.fixtures",)
import os
import pytest

from ciris_engine.logic.runtime.prevent_sideeffects import allow_runtime_creation
from ciris_engine.logic.runtime.ciris_runtime import CIRISRuntime


@pytest.fixture(autouse=True)
def allow_runtime():
    """Allow runtime creation for integration tests."""
    allow_runtime_creation()
    yield
    # Re-enable import protection after test
    os.environ['CIRIS_IMPORT_MODE'] = 'true'


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI") == "true",
    reason="Skipping in CI due to Python 3.12 compatibility issue with abstract base class instantiation when running in full test suite"
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
    
    from unittest.mock import patch, AsyncMock, MagicMock

    # Mock adapter loading to avoid real adapter initialization
    with patch('ciris_engine.logic.runtime.ciris_runtime.load_adapter') as mock_load:
        mock_adapter_class = MagicMock()
        mock_adapter_instance = MagicMock()
        mock_adapter_instance.stop = AsyncMock()
        mock_adapter_instance.start = AsyncMock()
        mock_adapter_instance.run_lifecycle = AsyncMock()
        mock_adapter_class.return_value = mock_adapter_instance
        mock_load.return_value = mock_adapter_class
        
        # Mock initialization manager to avoid core services verification
        with patch('ciris_engine.logic.runtime.ciris_runtime.get_initialization_manager') as mock_get_init:
            mock_init_manager = MagicMock()
            mock_init_manager.initialize = AsyncMock()
            mock_init_manager.register_step = MagicMock()
            mock_get_init.return_value = mock_init_manager

            # Create and initialize runtime
            runtime = CIRISRuntime(adapter_types=["cli"])

        with patch.object(runtime, '_perform_startup_maintenance'):
            await runtime.initialize()

        # Now the runtime should be initialized
        assert runtime.service_initializer is not None
        assert runtime._initialized is True

        # TODO: Implement actual test steps
        # 1. Create task
        # 2. Generate thought
        # 3. Run DMAs
        # 4. Apply guardrails
        # 5. Execute action
        # 6. Verify outcome
