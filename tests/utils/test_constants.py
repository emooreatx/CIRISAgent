import importlib
import os


def test_default_wa_fallback(monkeypatch):
    monkeypatch.delenv("WA_DISCORD_USER", raising=False)
    module = importlib.reload(importlib.import_module("ciris_engine.utils.constants"))
    assert module.DEFAULT_WA == "somecomputerguy"

    monkeypatch.setenv("WA_DISCORD_USER", "real_wa")
    module = importlib.reload(importlib.import_module("ciris_engine.utils.constants"))
    assert module.DEFAULT_WA == "real_wa"

