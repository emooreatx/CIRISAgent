import os
import importlib

def test_default_wa_env(monkeypatch):
    monkeypatch.setenv("WA_DISCORD_USER", "testuser")
    import ciris_engine.utils.constants as const
    importlib.reload(const)
    assert const.DEFAULT_WA == "testuser"
    assert isinstance(const.ENGINE_OVERVIEW_TEMPLATE, str)
    assert isinstance(const.MAX_THOUGHT_DEPTH, int)
    assert isinstance(const.MAX_PONDER_COUNT, int)
