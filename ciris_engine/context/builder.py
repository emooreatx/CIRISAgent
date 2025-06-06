from typing import Optional, Dict, Any, List
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, TaskContext, SystemSnapshot
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine.utils import GraphQLContextProvider
from ciris_engine import persistence
from pydantic import BaseModel
from ciris_engine.config.env_utils import get_env_var
from ciris_engine.secrets.service import SecretsService
from ciris_engine.schemas.context_schemas_v1 import SecretReference
import logging

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(
        self,
        memory_service: Optional[LocalGraphMemoryService] = None,
        graphql_provider: Optional[GraphQLContextProvider] = None,
        app_config: Optional[Any] = None,
        telemetry_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
    ) -> None:
        self.memory_service = memory_service
        self.graphql_provider = graphql_provider
        self.app_config = app_config
        self.telemetry_service = telemetry_service
        self.secrets_service = secrets_service or SecretsService()

    async def build_thought_context(
        self,
        thought: Thought,
        task: Optional[Task] = None
    ) -> ThoughtContext:
        """Build complete context for thought processing."""
        system_snapshot_data = await self.build_system_snapshot(task, thought)
        user_profiles_data = getattr(system_snapshot_data, 'user_profiles', None) or {}
        task_history_data = getattr(system_snapshot_data, 'recently_completed_tasks_summary', None) or []
        identity_context_str = self.memory_service.export_identity_context() if self.memory_service else None

        # --- Mission-Critical Channel ID Resolution ---
        channel_id = None
        resolution_source = "none"
        
        
        def safe_extract_channel_id(context: Any, source_name: str) -> Optional[str]:
            """Type-safe channel_id extraction."""
            if not context:
                return None
                
            try:
                if isinstance(context, dict):
                    cid = context.get('channel_id')
                    if cid is not None:
                        logger.info(f"Channel ID '{cid}' resolved from {source_name}")
                        return str(cid)
                elif hasattr(context, 'channel_id'):
                    cid = getattr(context, 'channel_id', None)
                    if cid is not None:
                        logger.info(f"Channel ID '{cid}' resolved from {source_name}")
                        return str(cid)
            except Exception as e:
                logger.error(f"Error extracting channel_id from {source_name}: {e}")
            
            return None
        
        # 1. Task context (highest priority)
        if task and task.context:
            channel_id = safe_extract_channel_id(task.context, "task.context")
            if channel_id:
                resolution_source = "task.context"
        
        # 2. Thought context
        if not channel_id and thought and thought.context:
            channel_id = safe_extract_channel_id(thought.context, "thought.context")
            if channel_id:
                resolution_source = "thought.context"
        
        # 3. Environment variable (for Discord)
        if not channel_id:
            env_channel_id = get_env_var("DISCORD_CHANNEL_ID")
            if env_channel_id:
                channel_id = env_channel_id
                resolution_source = "DISCORD_CHANNEL_ID env var"
                logger.info(f"Channel ID '{channel_id}' resolved from {resolution_source}")
        
        # 4. App config (structured fallback)
        if not channel_id and self.app_config:
            config_attrs = ['discord_channel_id', 'cli_channel_id', 'api_channel_id']
            for attr in config_attrs:
                if hasattr(self.app_config, attr):
                    config_channel_id = getattr(self.app_config, attr, None)
                    if config_channel_id:
                        channel_id = str(config_channel_id)
                        resolution_source = f"app_config.{attr}"
                        logger.info(f"Channel ID '{channel_id}' resolved from {resolution_source}")
                        break
        
        # 5. Mode-based fallback (last resort)
        if not channel_id and self.app_config:
            mode = getattr(self.app_config, 'agent_mode', '')
            mode_lower = mode.lower() if mode else ''
            if mode_lower == 'cli':
                channel_id = 'CLI'
                resolution_source = "CLI mode fallback"
            elif mode_lower == 'api':
                channel_id = 'API'
                resolution_source = "API mode fallback"
            elif mode == 'discord':
                channel_id = 'DISCORD_DEFAULT'
                resolution_source = "Discord mode fallback"
            
            if channel_id:
                logger.info(f"Channel ID '{channel_id}' resolved from {resolution_source}")
        
        # Final validation and logging
        if not channel_id:
            logger.warning("CRITICAL: Channel ID could not be resolved from any source - guardrails may receive None")
            # Set a safe default to prevent total failure
            channel_id = 'UNKNOWN'
            resolution_source = "emergency fallback"
        
        logger.info(f"Final channel_id resolution: '{channel_id}' from {resolution_source}")
        # Apply resolved channel_id to system snapshot
        if channel_id and hasattr(system_snapshot_data, 'channel_id'):
            system_snapshot_data.channel_id = channel_id
        
        # Build comprehensive channel context string
        channel_context_str = f"Our assigned channel is {channel_id} (resolved from {resolution_source})" if channel_id else None
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
                pass
        return ThoughtContext(
            system_snapshot=system_snapshot_data,
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

        # Mission-critical channel_id resolution with type safety
        channel_id = None
        
        def safe_extract_channel_id(context: Any, source_name: str) -> Optional[str]:
            """Type-safe channel_id extraction."""
            if not context:
                return None
                
            try:
                if isinstance(context, dict):
                    cid = context.get('channel_id')
                    return str(cid) if cid is not None else None
                elif hasattr(context, 'channel_id'):
                    cid = getattr(context, 'channel_id', None)
                    return str(cid) if cid is not None else None
            except Exception as e:
                logger.error(f"Error extracting channel_id from {source_name}: {e}")
            
            return None
        
        # Try task context first
        if task and task.context:
            channel_id = safe_extract_channel_id(task.context, "task.context")
        
        # Try thought context if not found
        if not channel_id and thought and thought.context:
            channel_id = safe_extract_channel_id(thought.context, "thought.context")
        
        if channel_id and self.memory_service:
            channel_node = GraphNode(
                id=f"channel/{channel_id}",
                type=NodeType.CHANNEL,
                scope=GraphScope.LOCAL
            )
            channel_info = await self.memory_service.recall(channel_node)

        recent_tasks_list: List[Any] = []
        db_recent_tasks = persistence.get_recent_completed_tasks(10)
        from ciris_engine.schemas.context_schemas_v1 import TaskSummary
        for t_obj in db_recent_tasks:
            if isinstance(t_obj, TaskSummary):
                pass
            elif isinstance(t_obj, BaseModel):
                recent_tasks_list.append(TaskSummary(**t_obj.model_dump()))
        top_tasks_list: List[Any] = []
        db_top_tasks = persistence.get_top_tasks(10)
        for t_obj in db_top_tasks:
            if isinstance(t_obj, TaskSummary):
                pass
            elif isinstance(t_obj, BaseModel):
                top_tasks_list.append(TaskSummary(**t_obj.model_dump()))
        current_task_summary = None
        if task:
            from ciris_engine.schemas.context_schemas_v1 import TaskSummary
            if isinstance(task, TaskSummary):
                current_task_summary = task
            elif isinstance(task, BaseModel):
                current_task_summary = TaskSummary(**task.model_dump())
            elif isinstance(task, dict):
                current_task_summary = TaskSummary(**task)
            else:
                current_task_summary = None

        # Get secrets information for the snapshot
        secrets_data = await self._build_secrets_snapshot()
        
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
            **secrets_data
        }
        if self.graphql_provider:
            graphql_extra_raw = await self.graphql_provider.enrich_context(task, thought)
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
        
        # Update snapshot with telemetry data if service is available
        if self.telemetry_service:
            await self.telemetry_service.update_system_snapshot(snapshot)
        
        return snapshot

    async def _build_secrets_snapshot(self) -> Dict[str, Any]:
        """Build secrets information for SystemSnapshot."""
        try:
            # Get recent secrets (limit to last 10 for context)
            all_secrets = await self.secrets_service.store.list_all_secrets()
            recent_secrets = sorted(all_secrets, key=lambda s: s.created_at, reverse=True)[:10]
            
            # Convert to SecretReference objects for the snapshot
            detected_secrets = [
                SecretReference(
                    uuid=secret.secret_uuid,
                    description=secret.description,
                    context_hint=secret.context_hint,
                    sensitivity=secret.sensitivity_level,
                    auto_decapsulate_actions=secret.auto_decapsulate_for_actions,
                    created_at=secret.created_at,
                    last_accessed=secret.last_accessed
                )
                for secret in recent_secrets
            ]
            
            # Get filter version
            filter_version = self.secrets_service.filter.config.version
            
            # Get total count
            total_secrets = len(all_secrets)
            
            return {
                "detected_secrets": detected_secrets,
                "secrets_filter_version": filter_version,
                "total_secrets_stored": total_secrets
            }
            
        except Exception as e:
            logger.error(f"Error building secrets snapshot: {e}")
            return {
                "detected_secrets": [],
                "secrets_filter_version": 0,
                "total_secrets_stored": 0
            }
