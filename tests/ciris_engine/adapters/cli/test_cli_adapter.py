import pytest
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.adapters.cli.cli_event_queues import CLIEventQueue
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage

@pytest.mark.asyncio
async def test_cli_adapter_send_message(capsys):
    queue = CLIEventQueue()
    adapter = CLIAdapter(queue, interactive=False)
    await adapter.send_message("cli", "hello")
    captured = capsys.readouterr()
    assert "[CLI][cli] hello" in captured.out

@pytest.mark.asyncio
async def test_cli_observer_handle_message():
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    queue = CLIEventQueue()
    observed = []

    async def on_obs(payload):
        observed.append(payload)

    observer = CLIObserver(on_obs, queue)
    msg = IncomingMessage(message_id="1", content="hi", author_id="u", author_name="User", channel_id="cli")
    await observer.handle_incoming_message(msg)
    assert observed and observed[0]["content"] == "hi"

@pytest.mark.asyncio
async def test_cli_observer_get_recent_messages():
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    queue = CLIEventQueue()
    async def noop(_):
        pass
    observer = CLIObserver(noop, queue)
    msg1 = IncomingMessage(message_id="1", content="a", author_id="u", author_name="User", channel_id="cli")
    msg2 = IncomingMessage(message_id="2", content="b", author_id="u", author_name="User", channel_id="cli")
    await observer.handle_incoming_message(msg1)
    await observer.handle_incoming_message(msg2)
    recent = await observer.get_recent_messages(limit=1)
    assert recent and recent[0]["id"] == "2"
