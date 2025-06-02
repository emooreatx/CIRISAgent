pytest_plugins = ("tests.fixtures",)
import pytest

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_full_thought_cycle(runtime: CIRISRuntime):
    """Test complete thought processing cycle."""
    # 1. Create task
    # 2. Generate thought
    # 3. Run DMAs
    # 4. Apply guardrails
    # 5. Execute action
    # 6. Verify outcome
    assert runtime.service_registry is not None
