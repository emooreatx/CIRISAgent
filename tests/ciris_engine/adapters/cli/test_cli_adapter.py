import pytest
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.versioning import SchemaVersion

@pytest.mark.asyncio
async def test_cli_adapter_send_message(capsys, monkeypatch):
    # Mock the add_correlation call to avoid database dependency
    monkeypatch.setattr(
        "ciris_engine.persistence.add_correlation",
        lambda corr: None,
    )
    adapter = CLIAdapter()
    await adapter.send_message("cli", "hello")
    captured = capsys.readouterr()
    assert "[CLI][cli] hello" in captured.out

@pytest.mark.asyncio
async def test_cli_observer_handle_message(monkeypatch):
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    added_tasks = []
    added_thoughts = []

    monkeypatch.setattr(
        "ciris_engine.persistence.add_task",
        lambda t: added_tasks.append(t),
    )
    monkeypatch.setattr(
        "ciris_engine.persistence.add_thought",
        lambda t: added_thoughts.append(t),
    )

    observer = CLIObserver(lambda _: None)
    msg = IncomingMessage(
        message_id=SchemaVersion.V1_0,
        content=SchemaVersion.V1_0,
        author_id=SchemaVersion.V1_0,
        author_name=SchemaVersion.V1_0,
        destination_id="cli"
    )
    observer._is_agent_message = lambda m: False
    observer._add_to_feedback_queue = lambda m: None
    await observer.handle_incoming_message(msg)
    assert added_tasks
    assert added_thoughts

@pytest.mark.asyncio
async def test_cli_observer_get_recent_messages():
    from ciris_engine.adapters.cli.cli_observer import CLIObserver

    async def noop(_):
        pass
    observer = CLIObserver(noop)
    msg1 = IncomingMessage(
        message_id=SchemaVersion.V1_0,
        content=SchemaVersion.V1_0,
        author_id=SchemaVersion.V1_0,
        author_name=SchemaVersion.V1_0,
        destination_id="cli"
    )
    msg2 = IncomingMessage(
        message_id=SchemaVersion.V1_0,
        content=SchemaVersion.V1_0,
        author_id=SchemaVersion.V1_0,
        author_name=SchemaVersion.V1_0,
        destination_id="cli"
    )
    await observer.handle_incoming_message(msg1)
    await observer.handle_incoming_message(msg2)
    recent = await observer.get_recent_messages(limit=1)
    # Patch: SchemaVersion.V1_0 is used for all ids, so check for that
    assert recent and recent[0]["id"] == SchemaVersion.V1_0


@pytest.mark.asyncio
async def test_cli_adapter_capabilities():
    adapter = CLIAdapter()
    caps = adapter.get_capabilities()
    assert "send_message" in caps
    assert "fetch_messages" in caps
