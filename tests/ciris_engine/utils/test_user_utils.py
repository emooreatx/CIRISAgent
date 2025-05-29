import pytest
from unittest.mock import patch, MagicMock
import asyncio
from ciris_engine.utils.user_utils import extract_user_nick

@pytest.mark.asyncio
async def test_extract_user_nick_message():
    class Author: display_name = "nick"; name = "name"
    class Msg: author = Author()
    nick = await extract_user_nick(message=Msg())
    assert nick == "nick"

@pytest.mark.asyncio
async def test_extract_user_nick_params():
    class Params: value = {"nick": "n"}
    nick = await extract_user_nick(params=Params())
    assert nick == "n"

@pytest.mark.asyncio
async def test_extract_user_nick_dispatch_context():
    nick = await extract_user_nick(dispatch_context={"author_name": "n"})
    assert nick == "n"

@pytest.mark.asyncio
@patch("ciris_engine.utils.user_utils.persistence.get_thought_by_id")
@patch("ciris_engine.utils.user_utils.persistence.get_task_by_id")
async def test_extract_user_nick_thought_id(mock_get_task, mock_get_thought):
    mock_get_thought.return_value = MagicMock(source_task_id="tid")
    mock_get_task.return_value = MagicMock(context={"author_name": "n"})
    nick = await extract_user_nick(thought_id="x")
    assert nick == "n"
