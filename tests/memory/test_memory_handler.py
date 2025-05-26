import pytest
from pathlib import Path
from datetime import datetime

from ciris_engine.memory.memory_handler import MemoryHandler, MemoryWrite
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.core.graph_schemas import GraphScope
from ciris_engine.core.agent_core_schemas import Thought, Task
from ciris_engine.core.foundational_schemas import ThoughtStatus, HandlerActionType
from ciris_engine.core import persistence


@pytest.fixture
def init_db(tmp_path: Path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(persistence, "get_sqlite_db_full_path", lambda: str(db_file))
    persistence.initialize_database()
    return db_file


@pytest.fixture
async def memory_service(tmp_path: Path):
    service = CIRISLocalGraph(str(tmp_path / "graph.pkl"))
    await service.start()
    yield service


def _create_task_and_thought(task_id: str, thought_id: str) -> Thought:
    now = datetime.utcnow().isoformat()
    task = Task(task_id=task_id, description="t", created_at=now, updated_at=now)
    persistence.add_task(task)
    thought = Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        thought_type="memory",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=0,
        content="",
    )
    persistence.add_thought(thought)
    return thought

def _create_thought(task_id: str, thought_id: str) -> Thought:
    now = datetime.utcnow().isoformat()
    thought = Thought(
        thought_id=thought_id,
        source_task_id=task_id,
        thought_type="memory",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        round_created=0,
        content="",
    )
    persistence.add_thought(thought)
    return thought


@pytest.mark.asyncio
async def test_user_metadata_writes_directly(init_db, memory_service):
    thought = _create_task_and_thought("task1", "th1")
    handler = MemoryHandler(memory_service)

    mem_write = MemoryWrite(key_path="user/@alice/nick", user_nick="alice", value="A")
    result = await handler.process_memorize(thought, mem_write)

    assert result is None
    updated = persistence.get_thought_by_id("th1")
    assert updated.status == ThoughtStatus.COMPLETED
    data = (await memory_service.remember("alice", GraphScope.LOCAL)).data
    assert data["nick"] == "A"


@pytest.mark.asyncio
async def test_channel_write_defers(init_db, memory_service):
    thought = _create_task_and_thought("task2", "th2")
    handler = MemoryHandler(memory_service)
    mem_write = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="Rules")

    result = await handler.process_memorize(thought, mem_write)

    assert result.selected_handler_action == HandlerActionType.DEFER
    updated = persistence.get_thought_by_id("th2")
    assert updated.status == ThoughtStatus.DEFERRED
    assert "alice" not in memory_service.graph


@pytest.mark.asyncio
async def test_wa_correction_applies(init_db, memory_service):
    original = _create_task_and_thought("task3", "th3")
    handler = MemoryHandler(memory_service)
    initial_write = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="Rules")
    await handler.process_memorize(original, initial_write)

    correction = _create_thought("task3", "th3c")
    correction.processing_context = {
        "is_wa_feedback": True,
        "corrected_thought_id": "th3",
        "feedback_target": "identity"
    }

    corrected_write = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="Rules updated")
    result = await handler.process_memorize(correction, corrected_write)

    assert result is None
    updated = persistence.get_thought_by_id("th3c")
    assert updated.status == ThoughtStatus.COMPLETED
    data = await memory_service.remember("alice", GraphScope.LOCAL)
    assert data.data.get("topic") == "Rules updated"


@pytest.mark.asyncio
async def test_double_deferral_prevented(init_db, memory_service):
    thought = _create_task_and_thought("task4", "th4")
    handler = MemoryHandler(memory_service)
    mem_write = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="Rules")

    correction = _create_thought("task4", "th5")
    correction.processing_context = {"is_wa_feedback": True, "feedback_target": "identity", "corrected_thought_id": "nonexistent"}

    result = await handler.process_memorize(correction, mem_write)

    assert result.selected_handler_action == HandlerActionType.DEFER
    updated = persistence.get_thought_by_id("th5")
    assert updated.status == ThoughtStatus.DEFERRED


@pytest.mark.asyncio
async def test_deferral_approval_roundtrip(init_db, memory_service):
    thought = _create_task_and_thought("task6", "th6")
    handler = MemoryHandler(memory_service)
    mem_write = MemoryWrite(key_path="channel/#general/topic", user_nick="bob", value="New rules")

    result = await handler.process_memorize(thought, mem_write)
    assert result.selected_handler_action == HandlerActionType.DEFER

    correction = _create_thought("task6", "th6c")
    correction.processing_context = {"is_wa_feedback": True, "feedback_target": "identity", "corrected_thought_id": "th6"}
    result2 = await handler.process_memorize(correction, mem_write)

    assert result2 is None
    data = (await memory_service.remember("bob", GraphScope.LOCAL)).data
    assert data.get("topic") == "New rules"
