from typing import Optional, Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought, Task
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, TaskContext, SystemSnapshot
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.utils import GraphQLContextProvider
from ciris_engine.config.env_utils import get_env_var
from ciris_engine.secrets.service import SecretsService
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
                        return str(cid)
                elif hasattr(context, 'channel_id'):
                    cid = getattr(context, 'channel_id', None)
                    if cid is not None:
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
        
        # 4. App config (structured fallback)
        if not channel_id and self.app_config:
            config_attrs = ['discord_channel_id', 'cli_channel_id', 'api_channel_id']
            for attr in config_attrs:
                if hasattr(self.app_config, attr):
                    config_channel_id = getattr(self.app_config, attr, None)
                    if config_channel_id:
                        channel_id = str(config_channel_id)
                        resolution_source = f"app_config.{attr}"
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
            
            # Removed verbose logging - adapters handle channel resolution
        
        # Final validation and logging
        if not channel_id:
            logger.warning("CRITICAL: Channel ID could not be resolved from any source - guardrails may receive None")
            # Set a safe default to prevent total failure
            channel_id = 'UNKNOWN'
            resolution_source = "emergency fallback"
        
        # Removed verbose logging - use debug level only
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
        return await _build_snapshot(
            task,
            thought,
            memory_service=self.memory_service,
            graphql_provider=self.graphql_provider,
            telemetry_service=self.telemetry_service,
            secrets_service=self.secrets_service,
        )

    async def _build_secrets_snapshot(self) -> Dict[str, Any]:
        """Build secrets information for SystemSnapshot."""
        return await _secrets_snapshot(self.secrets_service)
