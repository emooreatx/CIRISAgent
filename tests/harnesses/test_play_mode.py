import asyncio
import pytest

from ciris_engine.harnesses.play_mode import run_play_session
from ciris_engine.harnesses.solitude_mode import run_solitude_session
from ciris_engine.harnesses.reflection_scheduler import schedule_reflection_modes


@pytest.mark.asyncio
async def test_run_play_session_outputs(monkeypatch):
    outputs = []

    async def fake_sleep(duration):
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def capture(msg: str):
        outputs.append(msg)

    await run_play_session(capture, duration=0)
    assert outputs[0].startswith("A playful interval")
    assert outputs[-1].startswith("Play Mode complete")


@pytest.mark.asyncio
async def test_run_solitude_session_outputs(monkeypatch):
    outputs = []

    async def fake_sleep(duration):
        pass

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def capture(msg: str):
        outputs.append(msg)

    await run_solitude_session(capture, duration=0)
    assert outputs[0].startswith("A moment of solitude")
    assert outputs[-1].startswith("Solitude complete")


@pytest.mark.asyncio
async def test_scheduler_triggers_modes(monkeypatch):
    calls = []

    async def fake_sleep(_):
        calls.append("sleep")

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    async def fake_play(output_func, duration=0):
        calls.append("play")

    async def fake_sol(output_func, duration=0):
        calls.append("solitude")

    monkeypatch.setattr(
        'ciris_engine.harnesses.reflection_scheduler.run_play_session',
        fake_play
    )
    monkeypatch.setattr(
        'ciris_engine.harnesses.reflection_scheduler.run_solitude_session',
        fake_sol
    )

    async def output(msg: str):
        calls.append(f"msg:{msg}")

    await schedule_reflection_modes(output, interval=0, iterations=1)

    assert any(c in calls for c in ["play", "solitude"])
