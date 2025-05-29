import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ciris_engine.adapters.cli.cli_runtime import CLIRuntime, InteractiveCLIAdapter, CLIActionSink

@pytest.mark.asyncio
async def test_cli_runtime_initialization():
    runtime = CLIRuntime(profile_name="test_profile", interactive=False)
    assert runtime.profile_name == "test_profile"
    assert isinstance(runtime.action_sink, CLIActionSink)
    assert not runtime.interactive

@pytest.mark.asyncio
async def test_interactive_cli_adapter_fetch_inputs(monkeypatch):
    adapter = InteractiveCLIAdapter()
    # Simulate user input
    monkeypatch.setattr("builtins.input", lambda _: "test input")
    result = await adapter.fetch_inputs()
    assert result == []
    assert not adapter._should_stop

@pytest.mark.asyncio
async def test_interactive_cli_adapter_exit(monkeypatch):
    adapter = InteractiveCLIAdapter()
    monkeypatch.setattr("builtins.input", lambda _: "exit")
    result = await adapter.fetch_inputs()
    assert result == []
    assert adapter._should_stop

@pytest.mark.asyncio
async def test_cli_action_sink_methods():
    sink = CLIActionSink()
    await sink.start()
    await sink.stop()
    await sink.send_message("cli", "hello world")
    await sink.run_tool("echo", {"msg": "hi"})
