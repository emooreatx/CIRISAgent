from ciris_engine.utils.deferral_package_builder import build_deferral_package

def test_build_deferral_package_minimal():
    class Dummy:
        thought_id = "tid"
        content = "c"
        source_task_id = "ptid"
        system_snapshot = None
    thought = Dummy()
    parent_task = type("PT", (), {"description": "desc", "task_id": "ptid", "status": "PENDING", "priority": 1, "recent_actions": [], "completed_tasks": None, "channel_id": "chan"})()
    pkg = build_deferral_package(thought, parent_task)
    assert pkg["thought_id"] == "tid"
    assert pkg["parent_task_id"] == "ptid"
    assert "formatted_task_context" in pkg
