import asyncio
import pytest
from types import SimpleNamespace

from ciris_engine.harnesses.dream_benchmark import run_benchmark_suite


@pytest.mark.asyncio
async def test_run_benchmark_suite_limits_concurrency():
    calls = []
    max_active = 0
    current_active = 0

    async def fake_call(model_id: str, agent_id: str):
        nonlocal current_active, max_active
        current_active += 1
        max_active = max(max_active, current_active)
        await asyncio.sleep(0)
        current_active -= 1
        calls.append((model_id, agent_id))
        return {"model": model_id}

    client = SimpleNamespace(run_he300=fake_call, run_simplebench=fake_call)
    models = [f"m{i}" for i in range(20)]
    results = await run_benchmark_suite(client, models, "agent", max_concurrent=10)

    assert len(calls) == 40
    assert max_active <= 10
    assert set(results["he300"].keys()) == set(models)
    assert set(results["simplebench"].keys()) == set(models)
