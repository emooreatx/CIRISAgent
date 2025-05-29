import pytest
import asyncio
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph, GraphNode, NodeType, GraphScope, MemoryOpStatus
from ciris_engine.memory.memory_handler import MemoryHandler, MemoryWrite
from ciris_engine.memory.utils import is_wa_feedback, process_feedback
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus

@pytest.mark.asyncio
async def test_ciris_local_graph_memorize_and_remember():
    g = CIRISLocalGraph(storage_path=None)
    node = GraphNode(id="alice", type=NodeType.USER, scope=GraphScope.LOCAL, attributes={"foo": "bar"})
    result = await g.memorize(node)
    assert result.status == MemoryOpStatus.OK
    remembered = await g.remember("alice", GraphScope.LOCAL)
    assert remembered.status == MemoryOpStatus.OK
    assert remembered.data["foo"] == "bar"

@pytest.mark.asyncio
async def test_ciris_local_graph_forget():
    g = CIRISLocalGraph(storage_path=None)
    node = GraphNode(id="bob", type=NodeType.USER, scope=GraphScope.LOCAL, attributes={"x": 1})
    await g.memorize(node)
    result = await g.forget("bob", GraphScope.LOCAL)
    assert result.status == MemoryOpStatus.OK
    remembered = await g.remember("bob", GraphScope.LOCAL)
    assert remembered.data is None

def test_export_identity_context():
    g = CIRISLocalGraph(storage_path=None)
    node = GraphNode(id="id1", type=NodeType.USER, scope=GraphScope.IDENTITY, attributes={"role": "admin"})
    # Directly add to graph for test
    g._graphs[GraphScope.IDENTITY].add_node(node.id, **node.attributes)
    out = g.export_identity_context()
    assert "id1" in out and "admin" in out

@pytest.mark.asyncio
async def test_memory_handler_process_memorize_user(monkeypatch):
    g = CIRISLocalGraph(storage_path=None)
    handler = MemoryHandler(g)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", lambda *a, **k: None)
    thought = Thought(
        thought_id="th1", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test", context={},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    mw = MemoryWrite(key_path="user/alice/bio", user_nick="alice", value="bio text")
    result = await handler.process_memorize(thought, mw)
    assert result is None
    remembered = await g.remember("alice", GraphScope.LOCAL)
    assert remembered.data is not None

@pytest.mark.asyncio
async def test_memory_handler_process_memorize_channel_wa_feedback(monkeypatch):
    g = CIRISLocalGraph(storage_path=None)
    handler = MemoryHandler(g)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", lambda *a, **k: None)
    thought = Thought(
        thought_id="th2", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test",
        context={"is_wa_feedback": True, "feedback_target": "identity", "corrected_thought_id": "corr1"},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    mw = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="topic text")
    result = await handler.process_memorize(thought, mw)
    assert result is None  # Should complete
    remembered = await g.remember("alice", GraphScope.LOCAL)
    assert remembered.data is not None

@pytest.mark.asyncio
async def test_memory_handler_process_memorize_channel_wa_feedback_invalid(monkeypatch):
    g = CIRISLocalGraph(storage_path=None)
    handler = MemoryHandler(g)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", lambda *a, **k: None)
    thought = Thought(
        thought_id="th3", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test",
        context={"is_wa_feedback": True, "feedback_target": "identity", "corrected_thought_id": "nonexistent"},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    mw = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="topic text")
    result = await handler.process_memorize(thought, mw)
    assert result is not None
    assert result.selected_action.value == "defer"

@pytest.mark.asyncio
async def test_memory_handler_process_memorize_channel_wa_required(monkeypatch):
    g = CIRISLocalGraph(storage_path=None)
    handler = MemoryHandler(g)
    monkeypatch.setattr("ciris_engine.persistence.update_thought_status", lambda *a, **k: None)
    thought = Thought(
        thought_id="th4", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test",
        context={"feedback_target": "identity"},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    mw = MemoryWrite(key_path="channel/#general/topic", user_nick="alice", value="topic text")
    result = await handler.process_memorize(thought, mw)
    assert result is not None
    assert result.selected_action.value == "defer"

@pytest.mark.asyncio
async def test_process_feedback_identity(monkeypatch):
    g = CIRISLocalGraph(storage_path=None)
    # Patch update_identity_graph to check call
    called = {}
    async def fake_update_identity_graph(data):
        called["ok"] = True
        return "identity-updated"
    monkeypatch.setattr(g, "update_identity_graph", fake_update_identity_graph)
    thought = Thought(
        thought_id="th5", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test",
        context={"feedback_target": "identity", "feedback_data": {"wa_user_id": "u", "wa_authorized": True, "update_timestamp": "now", "nodes": [], "edges": []}},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    result = await process_feedback(thought, g)
    assert called["ok"] is True
    assert result == "identity-updated"

@pytest.mark.asyncio
async def test_process_feedback_invalid():
    g = CIRISLocalGraph(storage_path=None)
    thought = Thought(
        thought_id="th6", source_task_id="t1", thought_type="test", status=ThoughtStatus.PENDING,
        created_at="now", updated_at="now", round_number=1, content="test",
        context={"feedback_target": "unknown"},
        ponder_count=0, ponder_notes=None, parent_thought_id=None, final_action={}
    )
    result = process_feedback(thought, g)
    assert result.status.value == "denied"
