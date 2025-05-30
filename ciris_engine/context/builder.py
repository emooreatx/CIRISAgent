from typing import Optional, Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.schemas.graph_schemas_v1 import GraphScope # Corrected import for GraphScope
from ciris_engine.utils import GraphQLContextProvider
from pydantic import BaseModel
from os import getenv
import logging

logger = logging.getLogger(__name__) # Initialize logger

class ContextBuilder:
    def __init__(
        self,
        memory_service: Optional[CIRISLocalGraph] = None,
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
        user_profiles_data = system_snapshot_data.get("user_profiles", {})
        
        # Use recently_completed_tasks_summary from the snapshot as task_history
        task_history_data = system_snapshot_data.get("recently_completed_tasks_summary", [])
        
        identity_context_str = self.memory_service.export_identity_context() if self.memory_service else None
        
        # --- Add Discord channel context ---
        channel_id = None
        
        # Try to get channel_id from task context first
        if task and hasattr(task, 'context') and isinstance(task.context, dict):
            channel_id = task.context.get('channel_id')
        
        # Then try from thought context
        if not channel_id and hasattr(thought, 'context') and isinstance(thought.context, dict):
            channel_id = thought.context.get('channel_id')
        
        # Then try environment variable
        if not channel_id:
            channel_id = getenv("DISCORD_CHANNEL_ID")
        
        # Then try app_config
        if not channel_id and self.app_config and hasattr(self.app_config, 'discord_channel_id'):
            channel_id = self.app_config.discord_channel_id
        
        channel_context_str = None
        if channel_id:
            channel_context_str = f"Our assigned channel is {channel_id}"
            # Also add to system_snapshot_data for downstream use
            system_snapshot_data['channel_id'] = channel_id
        
        # Combine identity and channel context
        if identity_context_str and channel_context_str:
            identity_context_str = f"{identity_context_str}\n{channel_context_str}"
        elif channel_context_str:
            identity_context_str = channel_context_str
        
        return ThoughtContext(
            system_snapshot=system_snapshot_data,
            user_profiles=user_profiles_data,
            task_history=task_history_data,
            identity_context=identity_context_str
        )

    async def build_system_snapshot(
        self,
        task: Optional[Task],
        thought: Thought
    ) -> Dict[str, Any]:
        """Build system snapshot for the thought."""
        # This is the logic from WorkflowCoordinator.build_context
        thought_summary = None
        if thought:
            status_val = None
            if thought.status:
                if hasattr(thought.status, 'value'):
                    status_val = thought.status.value
                else:
                    status_val = str(thought.status)
            thought_type_val = thought.thought_type
            thought_summary = {
                "thought_id": thought.thought_id,
                "content": thought.content,
                "status": status_val,
                "source_task_id": thought.source_task_id,
                "thought_type": thought_type_val,
                "ponder_count": thought.ponder_count
            }

        # Add channel memory lookup for debugging
        channel_id = None 
        if task and hasattr(task, 'context') and task.context and 'channel_id' in task.context:
            channel_id = task.context['channel_id']
        elif thought and hasattr(thought, 'context') and thought.context and 'channel_id' in thought.context:
            channel_id = thought.context['channel_id']
        
        if channel_id and self.memory_service:
            logger.warning(f"DEBUG: Looking up channel {channel_id} in memory")
            channel_info = await self.memory_service.recall(f"channel/{channel_id}", GraphScope.LOCAL)
            logger.warning(f"DEBUG: Channel memory result: {channel_info}")

        # Recent and top tasks
        recent_tasks_list = []
        if self.memory_service:
            db_recent_tasks = self.memory_service.get_recent_completed_tasks(10)
        else:
            db_recent_tasks = []
        for t_obj in db_recent_tasks:
            if isinstance(t_obj, BaseModel):
                recent_tasks_list.append(t_obj.model_dump(mode='json', exclude_none=True))
            else:
                recent_tasks_list.append(t_obj)
        top_tasks_list = []
        if self.memory_service:
            db_top_tasks = self.memory_service.get_top_tasks(10)
        else:
            db_top_tasks = []
        for t_obj in db_top_tasks:
            if isinstance(t_obj, BaseModel):
                top_tasks_list.append({"task_id": t_obj.task_id, "description": t_obj.description, "priority": t_obj.priority})
            else:
                top_tasks_list.append(t_obj)
        context = {
            "current_task_details": task.model_dump(mode='json', exclude_none=True) if task and isinstance(task, BaseModel) else None,
            "current_thought_summary": thought_summary,
            "system_counts": {
                "total_tasks": self.memory_service.count_tasks() if self.memory_service else 0,
                "total_thoughts": self.memory_service.count_thoughts() if self.memory_service else 0, # This now correctly counts PENDING + PROCESSING
                "pending_tasks": self.memory_service.count_tasks("pending") if self.memory_service else 0,
                "pending_thoughts": self.memory_service.count_thoughts() if self.memory_service else 0, # Corrected: count_thoughts takes no args
            },
            "top_pending_tasks_summary": top_tasks_list,
            "recently_completed_tasks_summary": recent_tasks_list
        }
        # Enrich with GraphQL context if available
        if self.graphql_provider:
            graphql_extra_raw = await self.graphql_provider.enrich_context(task, thought)
            graphql_extra_processed = {}
            if "user_profiles" in graphql_extra_raw and isinstance(graphql_extra_raw["user_profiles"], dict):
                graphql_extra_processed["user_profiles"] = {}
                for key, profile_obj in graphql_extra_raw["user_profiles"].items():
                    if isinstance(profile_obj, BaseModel):
                        graphql_extra_processed["user_profiles"][key] = profile_obj.model_dump(mode='json', exclude_none=True)
                    else:
                        graphql_extra_processed["user_profiles"][key] = profile_obj
            for key, value in graphql_extra_raw.items():
                if key not in graphql_extra_processed:
                    if isinstance(value, BaseModel):
                        graphql_extra_processed[key] = value.model_dump(mode='json', exclude_none=True)
                    elif isinstance(value, list) and all(isinstance(item, BaseModel) for item in value):
                        graphql_extra_processed[key] = [item.model_dump(mode='json', exclude_none=True) for item in value]
                    else:
                        graphql_extra_processed[key] = value
            context.update(graphql_extra_processed)
        return context
