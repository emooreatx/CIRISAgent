import asyncio
import os
import signal
from types import SimpleNamespace

import pytest

from ciris_engine.harnesses import stop_mode
from ciris_engine.harnesses.stop_mode import StopHarness


@pytest.mark.asyncio
async def test_stop_harness_calls_stop():
    called = {"stop": False}

    async def stop_processing():
        called["stop"] = True

    processor = SimpleNamespace(stop_processing=stop_processing)
    harness = StopHarness(processor)

    with harness:
        harness._handle_signal(signal.SIGINT, None)
        await harness.wait_for_stop(poll_interval=0)

    assert called["stop"]


@pytest.mark.asyncio
async def test_version_gate_blocks(monkeypatch):
    monkeypatch.setattr(stop_mode, "__version__", "1.0.0")

    called = {"stop": False}

    async def stop_processing():
        called["stop"] = True

    processor = SimpleNamespace(stop_processing=stop_processing)
    harness = StopHarness(processor)

    os.environ["NEXT_AGENT_VERSION"] = "0.9.0"
    with harness:
        harness._handle_signal(signal.SIGTERM, None)
        await harness.wait_for_stop(poll_interval=0)
    os.environ.pop("NEXT_AGENT_VERSION")

    assert not called["stop"]
