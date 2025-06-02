import pytest
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

@pytest.mark.asyncio
async def test_cli_adapter_send_message(capsys):
    adapter = CLIAdapter(interactive=False)
    await adapter.send_message("cli", "hello")
    captured = capsys.readouterr()
    assert "[CLI][cli] hello" in captured.out

@pytest.mark.asyncio
async def test_cli_observer_handle_message(monkeypatch):
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    observed = []

    async def on_obs(payload):
        observed.append(payload)

    observer = CLIObserver(on_obs)
    # Ensure DISCORD_CHANNEL_ID is unset so CLIObserver falls back to 'cli'
    monkeypatch.delenv("DISCORD_CHANNEL_ID", raising=False)
    msg = IncomingMessage(message_id="1", content="hi", author_id="u", author_name="User", channel_id="cli")
    observer.multi_service_sink = object()
    observer._is_agent_message = lambda m: False
    observer._add_to_feedback_queue = lambda m: None
    async def fake_create_passive(msg):
        await on_obs({"message": {
            "message_id": msg.message_id,
            "content": msg.content,
            "author_id": msg.author_id,
            "author_name": msg.author_name,
            "channel_id": msg.channel_id,
            "timestamp": getattr(msg, "timestamp", None),
            "is_bot": getattr(msg, "is_bot", False),
            "is_dm": getattr(msg, "is_dm", False),
        }})
    observer._create_passive_observation_result = fake_create_passive
    await observer.handle_incoming_message(msg)
    assert observed and observed[0]["message"]["content"] == "hi"

@pytest.mark.asyncio
async def test_cli_observer_get_recent_messages():
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    async def noop(_):
        pass
    observer = CLIObserver(noop)
    msg1 = IncomingMessage(message_id="1", content="a", author_id="u", author_name="User", channel_id="cli")
    msg2 = IncomingMessage(message_id="2", content="b", author_id="u", author_name="User", channel_id="cli")
    await observer.handle_incoming_message(msg1)
    await observer.handle_incoming_message(msg2)
    recent = await observer.get_recent_messages(limit=1)
    assert recent and recent[0]["id"] == "2"


@pytest.mark.asyncio
async def test_cli_adapter_capabilities():
    adapter = CLIAdapter(interactive=False)
    caps = adapter.get_capabilities()
    assert "send_message" in caps
    assert "fetch_messages" in caps
