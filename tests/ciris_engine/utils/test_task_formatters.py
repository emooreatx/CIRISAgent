from ciris_engine.utils.task_formatters import format_task_context

def test_format_task_context_minimal():
    task = {"description": "desc", "task_id": "tid", "status": "PENDING", "priority": 1}
    out = format_task_context(task, [], None)
    assert "Current Task" in out
    assert "desc" in out
