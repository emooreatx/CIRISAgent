from typing import Optional, Any
from ciris_engine.schemas.runtime.models import Thought, Task
from ciris_engine.schemas.runtime.system_context import SystemSnapshot
from ciris_engine.schemas.runtime.models import TaskContext
from ciris_engine.schemas.runtime.processing_context import ThoughtContext
from ciris_engine.logic.services.memory_service import LocalGraphMemoryService
from ciris_engine.logic.utils import GraphQLContextProvider
from ciris_engine.logic.config.env_utils import get_env_var
from ciris_engine.logic.services.runtime.secrets_service import SecretsService
import logging
from .system_snapshot import build_system_snapshot as _build_snapshot
from .secrets_snapshot import build_secrets_snapshot as _secrets_snapshot

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(
        self,
        memory_service: Optional[LocalGraphMemoryService] = None,
        graphql_provider: Optional[GraphQLContextProvider] = None,
        app_config: Optional[Any] = None,
        telemetry_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        runtime: Optional[Any] = None,
        service_registry: Optional[Any] = None,
        resource_monitor: Optional[Any] = None,  # Will be REQUIRED
    ) -> None:
        self.memory_service = memory_service
        self.graphql_provider = graphql_provider
        self.app_config = app_config
        self.telemetry_service = telemetry_service
        self.secrets_service = secrets_service  # Must be provided, no fallback creation
        self.runtime = runtime
        self.service_registry = service_registry
        self.resource_monitor = resource_monitor

    async def build_thought_context(
        self,
        thought: Thought,
        task: Optional[Task] = None
    ) -> ThoughtContext:
        """Build complete context for thought processing."""
        system_snapshot_data = await self.build_system_snapshot(task, thought)
        user_profiles_data = getattr(system_snapshot_data, 'user_profiles', None) or {}
        task_history_data = getattr(system_snapshot_data, 'recently_completed_tasks_summary', None) or []
        
        # Get identity context from memory service
        identity_context_str = await self.memory_service.export_identity_context() if self.memory_service else None

        # --- Mission-Critical Channel ID Resolution ---
        channel_id = None
        resolution_source = "none"
        
        # First check if task.context has system_snapshot with channel_id
        if task and task.context and hasattr(task.context, 'system_snapshot') and task.context.system_snapshot and hasattr(task.context.system_snapshot, 'channel_id'):
            channel_id = task.context.system_snapshot.channel_id
            if channel_id:
                resolution_source = "task.context.system_snapshot.channel_id"
                logger.debug(f"Resolved channel_id '{channel_id}' from task.context.system_snapshot")
        
        
        def safe_extract_channel_id(context: Any, source_name: str) -> Optional[str]:
            """Type-safe channel_id extraction from nested context structures."""
            if not context:
                return None
                
            try:
                # Direct channel_id attribute
                if isinstance(context, dict):
                    cid = context.get('channel_id')
                    if cid is not None:
                        return str(cid)
                elif hasattr(context, 'channel_id'):
                    cid = getattr(context, 'channel_id', None)
                    if cid is not None:
                        return str(cid)
                
                # Check initial_task_context.channel_context.channel_id
                if hasattr(context, 'initial_task_context') and context.initial_task_context:
                    task_ctx = context.initial_task_context
                    if hasattr(task_ctx, 'channel_context') and task_ctx.channel_context:
                        channel_ctx = task_ctx.channel_context
                        if hasattr(channel_ctx, 'channel_id') and channel_ctx.channel_id:
                            return str(channel_ctx.channel_id)
                
                # Check system_snapshot.channel_context.channel_id
                if hasattr(context, 'system_snapshot') and context.system_snapshot:
                    snapshot = context.system_snapshot
                    if hasattr(snapshot, 'channel_context') and snapshot.channel_context:
                        channel_ctx = snapshot.channel_context
                        if hasattr(channel_ctx, 'channel_id') and channel_ctx.channel_id:
                            return str(channel_ctx.channel_id)
                            
            except Exception as e:
                logger.error(f"Error extracting channel_id from {source_name}: {e}")
            
            return None
        
        # PRIORITY: Check thought's simple context FIRST (most direct)
        if thought and hasattr(thought, 'context') and thought.context:
            # Check if it's a simple ThoughtContext with direct channel_id field
            if hasattr(thought.context, 'channel_id') and thought.context.channel_id:
                channel_id = str(thought.context.channel_id)
                resolution_source = "thought.context.channel_id"
                logger.debug(f"Resolved channel_id '{channel_id}' from thought.context.channel_id")
            else:
                # Try the complex extraction for ProcessingThoughtContext
                channel_id = safe_extract_channel_id(thought.context, "thought.context")
                if channel_id:
                    resolution_source = "thought.context (complex)"
                    logger.debug(f"Resolved channel_id '{channel_id}' from thought.context (complex extraction)")
                else:
                    logger.warning(f"Thought {getattr(thought, 'thought_id', 'unknown')} has context but no channel_id found in it")
        elif thought:
            logger.warning(f"Thought {getattr(thought, 'thought_id', 'unknown')} has no context at all")
        
        # If thought doesn't have channel_id, check task's direct channel_id field (it's required on Task model)
        if not channel_id and task and hasattr(task, 'channel_id') and task.channel_id:
            channel_id = str(task.channel_id)
            resolution_source = "task.channel_id"
            logger.warning(f"Thought missing channel_id, falling back to task.channel_id '{channel_id}' from task {task.task_id}")
        
        # Then check task context if thought didn't have it
        if not channel_id and task and task.context:
            channel_id = safe_extract_channel_id(task.context, "task.context")
            if channel_id:
                resolution_source = "task.context"
        
        if not channel_id and self.app_config and hasattr(self.app_config, 'home_channel'):
            home_channel = getattr(self.app_config, 'home_channel', None)
            if home_channel:
                channel_id = str(home_channel)
                resolution_source = "app_config.home_channel"
        
        if not channel_id:
            env_channel_id = get_env_var("DISCORD_CHANNEL_ID")
            if env_channel_id:
                channel_id = env_channel_id
                resolution_source = "DISCORD_CHANNEL_ID env var"
        
        if not channel_id and self.app_config:
            config_attrs = ['discord_channel_id', 'cli_channel_id', 'api_channel_id']
            for attr in config_attrs:
                if hasattr(self.app_config, attr):
                    config_channel_id = getattr(self.app_config, attr, None)
                    if config_channel_id:
                        channel_id = str(config_channel_id)
                        resolution_source = f"app_config.{attr}"
                        break
        
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
            
        
        # Check if system_snapshot_data already has a channel_id
        if not channel_id and hasattr(system_snapshot_data, 'channel_id') and system_snapshot_data.channel_id:
            channel_id = system_snapshot_data.channel_id
            resolution_source = "system_snapshot_data.channel_id"
            logger.debug(f"Using existing channel_id '{channel_id}' from system snapshot")
        
        if not channel_id:
            logger.warning("CRITICAL: Channel ID could not be resolved from any source - consciences may receive None")
            channel_id = 'UNKNOWN'
            resolution_source = "emergency fallback"
        
        # Only set channel_id if it's not already set in system_snapshot
        if channel_id and hasattr(system_snapshot_data, 'channel_id'):
            if not system_snapshot_data.channel_id:
                system_snapshot_data.channel_id = channel_id
            elif system_snapshot_data.channel_id != channel_id:
                logger.warning(f"System snapshot already has channel_id '{system_snapshot_data.channel_id}', not overwriting with '{channel_id}'")
        
        channel_context_str = f"Our assigned channel is {channel_id} (resolved from {resolution_source})" if channel_id else None
        if identity_context_str and channel_context_str:
            identity_context_str = f"{identity_context_str}\n{channel_context_str}"
        elif channel_context_str:
            identity_context_str = channel_context_str
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
        return await _build_snapshot(
            task,
            thought,
            self.resource_monitor,  # REQUIRED parameter must be positional
            memory_service=self.memory_service,
            graphql_provider=self.graphql_provider,
            telemetry_service=self.telemetry_service,
            secrets_service=self.secrets_service,
            runtime=self.runtime,
            service_registry=self.service_registry,
        )

    async def _build_secrets_snapshot(self) -> dict:
        """Build secrets information for SystemSnapshot."""
        return await _secrets_snapshot(self.secrets_service)
