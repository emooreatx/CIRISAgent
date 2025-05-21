import pytest
from ciris_engine.utils.task_formatters import format_task_context


def test_format_task_context_basic():
    current_task = {
        "description": "Handle customer issue",
        "task_id": "42",
        "status": "in_progress",
        "priority": "high",
    }
    recent_actions = [
        {
            "description": "Contacted customer",
            "outcome": "Awaiting reply",
            "updated_at": "2024-06-01 12:00",
        },
        {
            "description": "Escalated to tier 2",
            "outcome": "Pending",
            "updated_at": "2024-06-01 12:05",
        },
    ]
    completed_tasks = [
        {
            "description": "Resolved previous ticket",
            "outcome": "Issue fixed",
            "updated_at": "2024-06-01 11:00",
        }
    ]

    block = format_task_context(current_task, recent_actions, completed_tasks)
    assert "=== Current Task ===" in block
    assert "Handle customer issue" in block
    assert "1. Contacted customer" in block
    assert "Awaiting reply" in block
    assert "=== Last Completed Task ===" in block
    assert "Issue fixed" in block


def test_format_task_context_no_actions():
    block = format_task_context({"description": "d", "task_id": "1"}, [], [])
    assert "=== Current Task ===" in block
    assert "Recent Actions" not in block
    assert "Last Completed Task" not in block


