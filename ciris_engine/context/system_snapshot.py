from typing import Optional, Any, Dict, List
import logging
from pydantic import BaseModel
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.utils import GraphQLContextProvider
from ciris_engine.secrets.service import SecretsService
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine import persistence
from .secrets_snapshot import build_secrets_snapshot

logger = logging.getLogger(__name__)

async def build_system_snapshot(
    task: Optional[Task],
    thought: Any,
    memory_service: Optional[LocalGraphMemoryService] = None,
    graphql_provider: Optional[GraphQLContextProvider] = None,
    telemetry_service: Optional[Any] = None,
    secrets_service: Optional[SecretsService] = None,
) -> SystemSnapshot:
    """Build system snapshot for the thought."""
    from ciris_engine.schemas.context_schemas_v1 import ThoughtSummary, TaskSummary

    thought_summary = None
    if thought:
        status_val = getattr(thought, 'status', None)
        if status_val is not None and hasattr(status_val, 'value'):
            status_val = status_val.value
        elif status_val is not None:
            status_val = str(status_val)
        thought_type_val = getattr(thought, 'thought_type', None)
        thought_summary = ThoughtSummary(
            thought_id=getattr(thought, 'thought_id', None),
            content=getattr(thought, 'content', None),
            status=status_val,
            source_task_id=getattr(thought, 'source_task_id', None),
            thought_type=thought_type_val,
            ponder_count=getattr(thought, 'ponder_count', None),
        )

    # Mission-critical channel_id resolution with type safety
    channel_id = None

    def safe_extract_channel_id(context: Any, source_name: str) -> Optional[str]:
        if not context:
            return None
        try:
            if isinstance(context, dict):
                cid = context.get('channel_id')
                return str(cid) if cid is not None else None
            elif hasattr(context, 'channel_id'):
                cid = getattr(context, 'channel_id', None)
                return str(cid) if cid is not None else None
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error extracting channel_id from {source_name}: {e}")
        return None

    if task and task.context:
        channel_id = safe_extract_channel_id(task.context, "task.context")
    if not channel_id and thought and thought.context:
        channel_id = safe_extract_channel_id(thought.context, "thought.context")

    if channel_id and memory_service:
        channel_node = GraphNode(
            id=f"channel/{channel_id}",
            type=NodeType.CHANNEL,
            scope=GraphScope.LOCAL,
        )
        await memory_service.recall(channel_node)

    recent_tasks_list: List[Any] = []
    db_recent_tasks = persistence.get_recent_completed_tasks(10)
    for t_obj in db_recent_tasks:
        if isinstance(t_obj, TaskSummary):
            recent_tasks_list.append(t_obj)
        elif isinstance(t_obj, BaseModel):
            recent_tasks_list.append(TaskSummary(**t_obj.model_dump()))

    top_tasks_list: List[Any] = []
    db_top_tasks = persistence.get_top_tasks(10)
    for t_obj in db_top_tasks:
        if isinstance(t_obj, TaskSummary):
            top_tasks_list.append(t_obj)
        elif isinstance(t_obj, BaseModel):
            top_tasks_list.append(TaskSummary(**t_obj.model_dump()))

    current_task_summary = None
    if task:
        if isinstance(task, TaskSummary):
            current_task_summary = task
        elif isinstance(task, BaseModel):
            current_task_summary = TaskSummary(**task.model_dump())
        elif isinstance(task, dict):
            current_task_summary = TaskSummary(**task)

    secrets_data: Dict[str, Any] = {}
    if secrets_service:
        secrets_data = await build_secrets_snapshot(secrets_service)

    context_data = {
        "current_task_details": current_task_summary,
        "current_thought_summary": thought_summary,
        "system_counts": {
            "total_tasks": persistence.count_tasks(),
            "total_thoughts": persistence.count_thoughts(),
            "pending_tasks": persistence.count_tasks(TaskStatus.PENDING),
            "pending_thoughts": persistence.count_thoughts(),
        },
        "top_pending_tasks_summary": top_tasks_list,
        "recently_completed_tasks_summary": recent_tasks_list,
        "channel_id": channel_id,
        **secrets_data,
    }

    if graphql_provider:
        graphql_extra_raw = await graphql_provider.enrich_context(task, thought)
        graphql_extra_processed: Dict[str, Any] = {}
        if "user_profiles" in graphql_extra_raw and isinstance(graphql_extra_raw["user_profiles"], dict):
            graphql_extra_processed["user_profiles"] = {}
            for key, profile_obj in graphql_extra_raw["user_profiles"].items():
                graphql_extra_processed["user_profiles"][key] = profile_obj
        for key, value in graphql_extra_raw.items():
            if key not in graphql_extra_processed:
                graphql_extra_processed[key] = value
        context_data.update(graphql_extra_processed)

    snapshot = SystemSnapshot(**context_data)

    if telemetry_service:
        await telemetry_service.update_system_snapshot(snapshot)

    return snapshot
