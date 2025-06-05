import pytest
from ciris_engine.formatters import (
    format_system_snapshot,
    format_user_profiles,
    format_parent_task_chain,
    format_thoughts_chain,
    format_system_prompt_blocks,
    format_user_prompt_blocks,
    get_escalation_guidance,
)

def test_format_system_snapshot():
    from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
    snap = SystemSnapshot(system_counts={"pending_tasks": 2, "active_thoughts": 1, "completed_tasks": 5, "recent_errors": 0})
    out = format_system_snapshot(snap)
    assert "Pending Tasks: 2" in out
    assert "Active Thoughts: 1" in out
    assert "Completed Tasks: 5" in out
    assert "Recent Errors: 0" in out
    # Test missing fields
    snap2 = SystemSnapshot()
    out2 = format_system_snapshot(snap2)
    assert "Pending Tasks" not in out2

def test_format_user_profiles():
    # Empty
    assert format_user_profiles(None) == ""
    # One profile
    profiles = {"u1": {"name": "Alice", "interest": "math", "channel": "general"}}
    out = format_user_profiles(profiles)
    assert "Alice" in out and "math" in out and "general" in out
    # Multiple profiles
    profiles["u2"] = {"nick": "Bob"}
    out2 = format_user_profiles(profiles)
    assert "Bob" in out2

def test_format_parent_task_chain():
    # Empty
    assert "None" in format_parent_task_chain([])
    # Multi-level
    tasks = [
        {"task_id": "t1", "description": "root task"},
        {"task_id": "t2", "description": "parent task"},
        {"task_id": "t3", "description": "direct parent"},
    ]
    out = format_parent_task_chain(tasks)
    assert "Root Task" in out and "Direct Parent" in out

def test_format_thoughts_chain():
    # Empty
    assert "None" in format_thoughts_chain([])
    # Multi-thought
    thoughts = [
        {"content": "First thought"},
        {"content": "Second thought"},
    ]
    out = format_thoughts_chain(thoughts)
    assert "First thought" in out and "Active Thought" in out

def test_format_system_prompt_blocks():
    out = format_system_prompt_blocks(
        "IDENTITY", "TASK_HISTORY", "SYS_SNAP", "USER_PROFILES", "ESCALATE", "GUIDE"
    )
    assert "IDENTITY" in out and "ESCALATE" in out and "GUIDE" in out
    # Missing optional blocks
    out2 = format_system_prompt_blocks("A", "B", "C", "D")
    assert "A" in out2 and "D" in out2

def test_format_user_prompt_blocks():
    out = format_user_prompt_blocks("PARENT", "THOUGHTS", "SCHEMA")
    assert "PARENT" in out and "SCHEMA" in out
    out2 = format_user_prompt_blocks("PARENT", "THOUGHTS")
    assert "PARENT" in out2 and "THOUGHTS" in out2

def test_get_escalation_guidance():
    assert "EARLY" in get_escalation_guidance(0)
    assert "MID" in get_escalation_guidance(4)
    assert "LATE" in get_escalation_guidance(6)
    assert "EXHAUSTED" in get_escalation_guidance(7)
