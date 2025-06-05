from typing import Optional, Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, TaskContext, SystemSnapshot
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType # Corrected import for GraphScope
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus  # Add TaskStatus import
from ciris_engine.utils import GraphQLContextProvider
from ciris_engine import persistence  # Import persistence for proper task/thought access
from pydantic import BaseModel
from ciris_engine.config.env_utils import get_env_var
import logging

logger = logging.getLogger(__name__) # Initialize logger

class ContextBuilder:
    def __init__(
        self,
        memory_service: Optional[LocalGraphMemoryService] = None,
        graphql_provider: Optional[GraphQLContextProvider] = None,
        app_config: Optional[Any] = None,
    ):
        self.memory_service = memory_service
        self.graphql_provider = graphql_provider
        self.app_config = app_config

    async def build_thought_context(
        self,
        thought: Thought,
        task: Optional[Task] = None
    ) -> ThoughtContext:
        """Build complete context for thought processing."""
        system_snapshot_data = await self.build_system_snapshot(task, thought)
        
        # Extract user_profiles for the top-level field
        user_profiles_data = getattr(system_snapshot_data, 'user_profiles', None) or {}
        
        # Use recently_completed_tasks_summary from the snapshot as task_history
        task_history_data = getattr(system_snapshot_data, 'recently_completed_tasks_summary', None) or []
        
        identity_context_str = self.memory_service.export_identity_context() if self.memory_service else None
        
        # --- Add Discord channel context ---
        channel_id = None
        # Try to get channel_id from task context first
        if task and hasattr(task, 'context'):
            if isinstance(task.context, BaseModel):
                channel_id = getattr(task.context, 'channel_id', None)
            elif isinstance(task.context, dict):
                channel_id = task.context.get('channel_id')
        # Then try from thought context
        if not channel_id and hasattr(thought, 'context'):
            if isinstance(thought.context, BaseModel):
                channel_id = getattr(thought.context, 'channel_id', None)
            elif isinstance(thought.context, dict):
                channel_id = thought.context.get('channel_id')
        # Then try environment variable
        if not channel_id:
            channel_id = get_env_var("DISCORD_CHANNEL_ID")
        # Then try app_config
        if not channel_id and self.app_config and getattr(self.app_config, 'discord_channel_id', None):
            channel_id = self.app_config.discord_channel_id
        channel_context_str = None
        if channel_id:
            channel_context_str = f"Our assigned channel is {channel_id}"
        # Combine identity and channel context
        if identity_context_str and channel_context_str:
            identity_context_str = f"{identity_context_str}\n{channel_context_str}"
        elif channel_context_str:
            identity_context_str = channel_context_str
        # Extract initial_task_context from task if available
        initial_task_context = None
        if task and hasattr(task, 'context'):
            ctx = task.context
            if isinstance(ctx, ThoughtContext):
                initial_task_context = ctx.initial_task_context
            elif isinstance(ctx, TaskContext):
                initial_task_context = ctx
        
        # Create SystemSnapshot object from the data
        system_snapshot = system_snapshot_data
        
        return ThoughtContext(
            system_snapshot=system_snapshot,
            user_profiles=user_profiles_data,
            task_history=task_history_data,
            identity_context=identity_context_str,
            initial_task_context=initial_task_context
        )

    async def build_system_snapshot(
        self,
        task: Optional[Task],
        thought: Any  # Accept Thought or ProcessingQueueItem
    ) -> SystemSnapshot:
        """Build system snapshot for the thought."""
        # This is the logic from WorkflowCoordinator.build_context
        from ciris_engine.schemas.context_schemas_v1 import ThoughtSummary
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
                ponder_count=getattr(thought, 'ponder_count', None)
            )

        # Add channel memory lookup for debugging
        channel_id = None
        if task and hasattr(task, 'context'):
            if isinstance(task.context, BaseModel) and getattr(task.context, 'channel_id', None):
                channel_id = getattr(task.context, 'channel_id', None)
            elif isinstance(task.context, dict):
                channel_id = task.context.get('channel_id')
        if not channel_id and thought and hasattr(thought, 'context'):
            if isinstance(thought.context, BaseModel) and getattr(thought.context, 'channel_id', None):
                channel_id = getattr(thought.context, 'channel_id', None)
            elif isinstance(thought.context, dict):
                channel_id = thought.context.get('channel_id')
        
        if channel_id and self.memory_service:
            logger.warning(f"DEBUG: Looking up channel {channel_id} in memory")
            channel_node = GraphNode(
                id=f"channel/{channel_id}",
                type=NodeType.CHANNEL,
                scope=GraphScope.LOCAL
            )
            channel_info = await self.memory_service.recall(channel_node)
            logger.warning(f"DEBUG: Channel memory result: {channel_info}")

        # Recent and top tasks
        recent_tasks_list = []
        db_recent_tasks = persistence.get_recent_completed_tasks(10)
        from ciris_engine.schemas.context_schemas_v1 import TaskSummary
        for t_obj in db_recent_tasks:
            if isinstance(t_obj, TaskSummary):
                recent_tasks_list.append(t_obj)
            elif isinstance(t_obj, BaseModel):
                recent_tasks_list.append(TaskSummary(**t_obj.model_dump()))
            elif isinstance(t_obj, dict):
                recent_tasks_list.append(TaskSummary(**t_obj))
        top_tasks_list = []
        db_top_tasks = persistence.get_top_tasks(10)
        for t_obj in db_top_tasks:
            if isinstance(t_obj, TaskSummary):
                top_tasks_list.append(t_obj)
            elif isinstance(t_obj, BaseModel):
                top_tasks_list.append(TaskSummary(**t_obj.model_dump()))
            elif isinstance(t_obj, dict):
                top_tasks_list.append(TaskSummary(**t_obj))
        current_task_summary = None
        if task:
            from ciris_engine.schemas.context_schemas_v1 import TaskSummary
            if isinstance(task, TaskSummary):
                current_task_summary = task
            elif isinstance(task, BaseModel):
                current_task_summary = TaskSummary(**task.model_dump())
            elif isinstance(task, dict):
                # Ideally task should never be a plain dict but handle defensively
                current_task_summary = TaskSummary(**task)

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
            "channel_id": channel_id
        }
        # Enrich with GraphQL context if available
        if self.graphql_provider:
            graphql_extra_raw = await self.graphql_provider.enrich_context(task, thought)
            graphql_extra_processed = {}
            if "user_profiles" in graphql_extra_raw and isinstance(graphql_extra_raw["user_profiles"], dict):
                graphql_extra_processed["user_profiles"] = {}
                for key, profile_obj in graphql_extra_raw["user_profiles"].items():
                    graphql_extra_processed["user_profiles"][key] = profile_obj
            for key, value in graphql_extra_raw.items():
                if key not in graphql_extra_processed:
                    graphql_extra_processed[key] = value
            context_data.update(graphql_extra_processed)
        
        return SystemSnapshot(**context_data)
