"""Test helper functions for CIRIS Engine tests."""
from datetime import datetime, timezone
from typing import Optional
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, DispatchContext
from ciris_engine.schemas.context_schemas_v1 import ChannelContext
from ciris_engine.utils.channel_utils import create_channel_context


def create_test_dispatch_context(
    channel_id: Optional[str] = "test_channel",
    channel_context: Optional[ChannelContext] = None,
    author_id: str = "test_author",
    author_name: str = "Test Author",
    origin_service: str = "test_service",
    handler_name: str = "test_handler",
    action_type: HandlerActionType = HandlerActionType.SPEAK,
    thought_id: str = "test_thought_1",
    task_id: str = "test_task_1",
    source_task_id: str = "test_source_1",
    event_summary: str = "Test event",
    event_timestamp: Optional[str] = None,
    wa_id: Optional[str] = None,
    wa_authorized: bool = False,
    correlation_id: str = "test_correlation_1",
    round_number: int = 1,
    guardrail_result: Optional[any] = None
) -> DispatchContext:
    """Create a DispatchContext with all required fields for testing."""
    if event_timestamp is None:
        event_timestamp = datetime.now(timezone.utc).isoformat()
    
    # Create channel context if not provided
    if channel_context is None:
        if channel_id:
            channel_context = create_channel_context(channel_id, channel_type="test")
        else:
            # Create a minimal channel context for tests that require empty channel_id
            channel_context = ChannelContext(
                adapter_id="test:empty",
                channel_id="",
                channel_type="test"
            )
    
    return DispatchContext(
        channel_context=channel_context,
        author_id=author_id,
        author_name=author_name,
        origin_service=origin_service,
        handler_name=handler_name,
        action_type=action_type,
        thought_id=thought_id,
        task_id=task_id,
        source_task_id=source_task_id,
        event_summary=event_summary,
        event_timestamp=event_timestamp,
        wa_id=wa_id,
        wa_authorized=wa_authorized,
        correlation_id=correlation_id,
        round_number=round_number,
        guardrail_result=guardrail_result
    )