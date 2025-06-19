import pytest
from datetime import datetime, timezone
from ciris_engine.processor.thought_manager import ThoughtManager
from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from unittest.mock import patch

@pytest.fixture
def sample_task():
    from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
    context = ThoughtContext(
        system_snapshot=SystemSnapshot(),
        initial_task_context={
            "custom_key": "custom_value"
        },
        author_name="TestUser",
        author_id="user-123",
        channel_id="chan-456",
        origin_service="CLI"
    )
    return Task(
        task_id="task-ctx-1",
        description="Test task for context propagation",
        status=TaskStatus.PENDING,
        priority=1,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        context=context,
    )

def test_seed_thought_context_propagation(sample_task):
    tm = ThoughtManager(default_channel_id="default-chan")
    with patch("ciris_engine.persistence.add_thought") as mock_add:
        thought = tm.generate_seed_thought(sample_task, round_number=1)
        assert thought is not None
        # Check that context is a ThoughtContext object
        assert thought.context is not None
        assert hasattr(thought.context, 'initial_task_context')
        
        # Custom key should be in initial_task_context
        assert thought.context.initial_task_context is not None
        assert hasattr(thought.context.initial_task_context, 'custom_key')
        assert thought.context.initial_task_context.custom_key == "custom_value"
        # Should not mutate the original task context
        assert thought.context is not sample_task.context
        # Should call persistence.add_thought
        mock_add.assert_called_once()

def test_followup_thought_context_copy(sample_task):
    tm = ThoughtManager(default_channel_id="default-chan")
    with patch("ciris_engine.persistence.add_thought") as mock_add:
        seed = tm.generate_seed_thought(sample_task, round_number=1)
        followup = tm.create_follow_up_thought(seed, content="Follow up", round_number=2)
        assert followup is not None
        # Context should be copied from parent
        assert followup.context == seed.context
        # Should call persistence.add_thought for followup
        assert mock_add.call_count == 2

def test_queue_and_processing_context_integrity(sample_task):
    tm = ThoughtManager(default_channel_id="default-chan")
    with patch("ciris_engine.persistence.add_thought") as mock_add, \
         patch("ciris_engine.persistence.get_pending_thoughts_for_active_tasks", return_value=[]):
        seed = tm.generate_seed_thought(sample_task, round_number=1)
        # Simulate queue population
        tm.processing_queue.appendleft(ProcessingQueueItem.from_thought(seed))
        batch = tm.get_queue_batch()
        assert batch
        # Mark as processing should not alter context
        with patch("ciris_engine.persistence.update_thought_status", return_value=True):
            updated = tm.mark_thoughts_processing(batch, round_number=1)
            assert updated
            for item in updated:
                # Fetch the original thought and check context
                assert hasattr(item, "thought_id")
                # No context mutation expected
