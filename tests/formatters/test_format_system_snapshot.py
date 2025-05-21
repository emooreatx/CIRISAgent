from ciris_engine.formatters.system_snapshot import format_system_snapshot


def test_format_system_snapshot():
    snapshot = {
        "pending_tasks": 4,
        "active_thoughts": 1,
        "completed_tasks": 22,
        "recent_errors": 0,
    }
    block = format_system_snapshot(snapshot)
    assert "=== System Snapshot ===" in block
    assert "Pending Tasks: 4" in block
    assert "Active Thoughts: 1" in block
