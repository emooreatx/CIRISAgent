import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

@pytest.mark.asyncio
async def test_handle_discord_observe_event_passive(monkeypatch):
    add_task = MagicMock()
    task_exists = MagicMock(return_value=False)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.add_task', add_task)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.task_exists', task_exists)

    payload = {'message_id': 'm1', 'content': 'hello'}
    result = await handle_discord_observe_event(payload, mode='passive')

    assert result.selected_action == HandlerActionType.OBSERVE
    assert result.action_parameters['task_id'] == 'm1'
    add_task.assert_called_once()

@pytest.mark.asyncio
async def test_handle_discord_observe_event_active(monkeypatch):
    add_task = MagicMock()
    task_exists = MagicMock(return_value=False)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.add_task', add_task)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.task_exists', task_exists)

    # Create fake message objects with required attributes
    class FakeAuthor:
        def __init__(self, id):
            self.id = id
    class FakeMessage:
        def __init__(self, id, content, author_id, created_at=None):
            self.id = id
            self.content = content
            self.author = FakeAuthor(author_id)
            self.created_at = created_at
    import datetime
    fake_messages = [
        FakeMessage('m1', 'hi', 'a1', datetime.datetime(2024, 1, 1, 12, 0, 0)),
        FakeMessage('m2', 'yo', 'a2', datetime.datetime(2024, 1, 1, 12, 1, 0)),
    ]

    # Mock channel.history to yield fake messages
    class FakeHistory:
        def __init__(self, messages):
            self._messages = messages
        def __aiter__(self):
            self._iter = iter(self._messages)
            return self
        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration
    class FakeChannel:
        def __init__(self, messages):
            self._messages = messages
        def history(self, limit=20):
            return FakeHistory(self._messages)
    fake_channel = FakeChannel(fake_messages)

    discord_service = Mock()
    discord_service.get_channel.return_value = fake_channel
    context = {'discord_service': discord_service, 'default_channel_id': 12345}

    class DummyTask(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.Task', DummyTask, raising=False)

    payload = {'channel_id': 12345}
    result = await handle_discord_observe_event(payload, mode='active', context=context)

    discord_service.get_channel.assert_called_with(12345)
    assert result.selected_action == HandlerActionType.OBSERVE
    assert 'observation_summary' in result.action_parameters
    assert result.action_parameters['channel_id'] == 12345
    assert result.action_parameters['message_count'] == 2
