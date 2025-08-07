"""Test that TSDBDataConverter properly handles None values from database.

This test ensures that the converter can handle NULL database values
that become None in Python dicts, which was causing validation errors
in production.
"""

from ciris_engine.logic.services.graph.tsdb_consolidation.data_converter import RawThoughtData, TSDBDataConverter


def test_thought_with_none_final_action():
    """Test that thoughts with None final_action are handled correctly."""
    # This simulates what comes from the database when final_action_json is NULL
    raw_thought_dict = {
        "thought_id": "test_thought_1",
        "thought_type": "standard",
        "status": "completed",
        "created_at": "2025-08-07T00:00:00",
        "final_action": None,  # This is what causes the issue in production
        "content": "Test thought content",
    }

    # This should not raise a validation error
    result = TSDBDataConverter._convert_thought(raw_thought_dict)

    assert result is not None
    assert result.thought_id == "test_thought_1"
    assert result.final_action is None
    assert result.handler is None


def test_task_with_thoughts_containing_none():
    """Test that tasks with thoughts containing None values are handled."""
    raw_task_dict = {
        "task_id": "test_task_1",
        "status": "completed",
        "created_at": "2025-08-07T00:00:00",
        "updated_at": "2025-08-07T00:01:00",
        "thoughts": [
            {
                "thought_id": "thought_1",
                "thought_type": "standard",
                "status": "completed",
                "created_at": "2025-08-07T00:00:00",
                "final_action": None,  # NULL from database
            },
            {
                "thought_id": "thought_2",
                "thought_type": "standard",
                "status": "completed",
                "created_at": "2025-08-07T00:00:30",
                "final_action": '{"action": "SPEAK"}',  # Valid JSON string
            },
        ],
    }

    # This should not raise a validation error
    result = TSDBDataConverter.convert_task(raw_task_dict)

    assert result is not None
    assert result.task_id == "test_task_1"
    assert len(result.thoughts) == 2
    assert result.thoughts[0].final_action is None
    assert result.thoughts[1].final_action is not None


def test_raw_thought_data_with_none_directly():
    """Test that RawThoughtData can be created when None values are filtered."""
    # This would fail without the fix
    raw_dict_with_none = {
        "thought_id": "test",
        "thought_type": "standard",
        "status": "completed",
        "created_at": "2025-08-07T00:00:00",
        "final_action": None,
    }

    # Filter None values as the fix does
    cleaned_dict = {k: v for k, v in raw_dict_with_none.items() if v is not None}

    # This should work
    thought = RawThoughtData(**cleaned_dict)
    assert thought.thought_id == "test"
    assert thought.final_action is None  # Optional field defaults to None


def test_multiple_none_fields():
    """Test handling of multiple None fields in thought data."""
    raw_thought_dict = {
        "thought_id": "test_thought",
        "thought_type": "standard",
        "status": "completed",
        "created_at": "2025-08-07T00:00:00",
        "final_action": None,
        "content": None,
        "round_number": None,  # These would all come as None from NULL database values
        "depth": None,
    }

    result = TSDBDataConverter._convert_thought(raw_thought_dict)

    assert result is not None
    assert result.thought_id == "test_thought"
    assert result.final_action is None
    assert result.handler is None
