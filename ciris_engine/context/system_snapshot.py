from typing import Optional, Any, Dict, List
import logging
from pydantic import BaseModel
from ciris_engine.services.memory_service import LocalGraphMemoryService
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
        thought_id_val = getattr(thought, 'thought_id', None)
        if thought_id_val is None:
            thought_id_val = "unknown"  # Provide a default value for required field
        thought_summary = ThoughtSummary(
            thought_id=thought_id_val,
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
            # First check if context has system_snapshot.channel_id
            if hasattr(context, 'system_snapshot') and hasattr(context.system_snapshot, 'channel_id'):
                cid = context.system_snapshot.channel_id
                if cid is not None:
                    logger.debug(f"Found channel_id '{cid}' in {source_name}.system_snapshot.channel_id")
                    return str(cid)
            
            # Then check direct channel_id attribute
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
    
    # Retrieve agent identity from graph - SINGLE CALL at snapshot generation
    identity_data: Dict[str, Any] = {}
    identity_purpose: Optional[str] = None
    identity_capabilities: List[str] = []
    identity_restrictions: List[str] = []
    
    if memory_service:
        try:
            # Get the agent's identity node from the graph
            identity_node = GraphNode(
                id="agent/identity",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY
            )
            identity_result = await memory_service.recall(identity_node)
            
            if identity_result and identity_result.data:
                # MemoryOpResult returns data, not nodes
                identity_data = identity_result.data.get("identity", {}) if isinstance(identity_result.data, dict) else {}
                identity_purpose = identity_data.get("purpose_statement", "")
                identity_capabilities = identity_data.get("allowed_capabilities", [])
                identity_restrictions = identity_data.get("restricted_capabilities", [])
        except Exception as e:
            logger.warning(f"Failed to retrieve agent identity from graph: {e}")

    recent_tasks_list: List[Any] = []
    db_recent_tasks = persistence.get_recent_completed_tasks(10)
    for t_obj in db_recent_tasks:
        # db_recent_tasks returns list[Task], convert to TaskSummary
        if isinstance(t_obj, BaseModel):
            recent_tasks_list.append(TaskSummary(**t_obj.model_dump()))

    top_tasks_list: List[Any] = []
    db_top_tasks = persistence.get_top_tasks(10)
    for t_obj in db_top_tasks:
        # db_top_tasks returns list[Task], convert to TaskSummary
        if isinstance(t_obj, BaseModel):
            top_tasks_list.append(TaskSummary(**t_obj.model_dump()))

    current_task_summary = None
    if task:
        # Convert Task to TaskSummary
        if isinstance(task, BaseModel):
            current_task_summary = TaskSummary(**task.model_dump())

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
        # Identity graph data - loaded once per snapshot
        "agent_identity": identity_data,
        "identity_purpose": identity_purpose,
        "identity_capabilities": identity_capabilities,
        "identity_restrictions": identity_restrictions,
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
