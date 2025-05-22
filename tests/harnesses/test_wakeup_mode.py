import pytest
from types import SimpleNamespace

from ciris_engine.harnesses.wakeup_mode import run_wakeup


@pytest.mark.asyncio
async def test_run_wakeup_invokes_processor():
    called = False

    async def fake_wakeup():
        nonlocal called
        called = True
        return True

    processor = SimpleNamespace(_run_wakeup_sequence=fake_wakeup)
    result = await run_wakeup(processor)

    assert called is True
    assert result is True
