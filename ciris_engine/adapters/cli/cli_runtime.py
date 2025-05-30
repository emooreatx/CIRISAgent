import asyncio
import logging
from typing import Optional, List, Any
import uuid
from datetime import datetime, timezone

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
from ciris_engine.ports import ActionSink
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine import persistence
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher

logger = logging.getLogger(__name__)

class CLIActionSink(ActionSink):
    async def start(self) -> None:
        pass
    async def stop(self) -> None:
        pass
    async def _process_action(self, action: Any):
        """Process a single action - CLI implementation"""
        action_type = getattr(action, 'action_type', getattr(action, 'type', 'unknown'))
        
        if hasattr(action, 'channel_id') and hasattr(action, 'content'):
            # Send message action
            await self.send_message(action.channel_id, action.content)
        elif hasattr(action, 'tool_name') and hasattr(action, 'args'):
            # Tool action
            await self.run_tool(action.tool_name, action.args)
        elif hasattr(action, 'name') and hasattr(action, 'args'):
            # Alternative tool action format
            await self.run_tool(action.name, action.args)
        else:
            logger.warning(f"CLIActionSink: Unknown action format: {action}")
    async def send_message(self, channel_id: str, content: str) -> None:
        print(f"\n[CIRIS] {content}\n")
    async def run_tool(self, name: str, args: dict) -> None:
        print(f"[TOOL] {name}: {args}")

class InteractiveCLIAdapter(CLIAdapter):
    def __init__(self):
        super().__init__()
        self._should_stop = False
        self._observe_handler = None

    def set_observe_handler(self, observe_handler):
        """Set the observe handler callback for processing user input."""
        self._observe_handler = observe_handler

    async def start(self):
        """Start the interactive CLI adapter."""
        pass

    async def stop(self):
        """Stop the interactive CLI adapter."""
        self._should_stop = True

    async def fetch_inputs(self) -> List[Any]:
        if self._should_stop:
            return []
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, input, "\n>>> ")
            if not line:
                return []
            if line.lower() in ["exit", "quit", "bye"]:
                self._should_stop = True
                print("Goodbye!")
                return []
            
            # Generate a unique message ID for this CLI input
            message_id = f"cli_{uuid.uuid4().hex[:8]}"
            
            # Create observation payload for passive observe handling
            payload = {
                "message_id": message_id,
                "content": line,
                "context": {
                    "origin_service": "cli",
                    "author_id": "local_user",
                    "author_name": "User",
                    "channel_id": "cli",
                },
                "task_description": (
                    f"Observed user 'User' in CLI say: '{line}'. "
                    "Evaluate and decide on the appropriate course of action."
                ),
            }
            
            # Send through observe handler if available
            if self._observe_handler:
                try:
                    from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
                    # Use CLI-aware context for observe handler
                    context = {"agent_mode": "cli"}
                    await handle_discord_observe_event(payload, mode="passive", context=context)
                    logger.info(f"Sent CLI input to observe queue: {message_id}")
                except Exception as e:
                    logger.error(f"Error processing CLI input through observe handler: {e}")
                    # Fallback: create task directly
                    await self._create_task_fallback(message_id, line)
            else:
                # Fallback: create task directly if no observe handler
                await self._create_task_fallback(message_id, line)
            
            return []
        except EOFError:
            self._should_stop = True
            return []

    async def _create_task_fallback(self, task_id: str, content: str):
        """Fallback method to create task directly if observe handler is not available."""
        now = datetime.now(timezone.utc).isoformat()
        task = Task(
            task_id=task_id,
            description=content,
            status=TaskStatus.PENDING,
            priority=1,
            created_at=now,
            updated_at=now,
            context={
                "origin_service": "cli",
                "author_id": "local_user",
                "author_name": "User",
                "channel_id": "cli",
                "content": content,
            }
        )
        # Ensure the database is initialized before adding the task
        persistence.initialize_database()
        persistence.add_task(task)
        logger.info(f"Created task {task_id} from CLI input (fallback)")
        return task

class CLIRuntime(CIRISRuntime):
    def __init__(self, profile_name: str = "default", interactive: bool = True):
        cli_adapter = InteractiveCLIAdapter() if interactive else CLIAdapter()
        super().__init__(
            profile_name=profile_name,
            io_adapter=cli_adapter,
            startup_channel_id="cli",
        )
        # Create action sink early
        self.action_sink = CLIActionSink()
        self.interactive = interactive
        
    async def initialize(self):
        """Initialize CLI-specific components."""
        await super().initialize()
        
        # Set up observe handler for CLI input processing
        if isinstance(self.io_adapter, InteractiveCLIAdapter):
            # Create observe handler callback that mimics Discord's pattern
            async def cli_observe_handler(payload):
                """Handle CLI observe events (mimics Discord observer pattern)."""
                try:
                    from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
                    # Add CLI-specific context
                    context = {"agent_mode": "cli"}
                    await handle_discord_observe_event(payload, mode="passive", context=context)
                    logger.debug(f"Processed CLI observe event: {payload.get('message_id')}")
                except Exception as e:
                    logger.error(f"Error in CLI observe handler: {e}")
            
            self.io_adapter.set_observe_handler(cli_observe_handler)
        
        # Update action_sink in dependencies after initialization
        if self.agent_processor and self.agent_processor.thought_processor:
            dependencies = getattr(self.agent_processor.thought_processor, 'dependencies', None)
            if dependencies:
                dependencies.action_sink = self.action_sink
                
            # Also update all handlers' dependencies
            if hasattr(self.agent_processor, 'action_dispatcher') and self.agent_processor.action_dispatcher:
                for handler in self.agent_processor.action_dispatcher.handlers.values():
                    if hasattr(handler, 'dependencies'):
                        handler.dependencies.action_sink = self.action_sink
                        
        # Rebuild action dispatcher with proper action_sink
        if self.agent_processor:
            new_dispatcher = await self._build_action_dispatcher(dependencies)
            self.agent_processor.action_dispatcher = new_dispatcher
        
    async def _build_action_dispatcher(self, dependencies):
        return build_action_dispatcher(
            audit_service=self.audit_service,
            max_ponder_rounds=self.app_config.workflow.max_ponder_rounds,
            action_sink=self.action_sink,
            memory_service=self.memory_service,
        )
    async def run(self, max_rounds: Optional[int] = None):
        if self.interactive:
            print("\n" + "="*60)
            print("CIRIS Agent - Interactive CLI Mode")
            print(f"Profile: {self.profile_name}")
            print("Type 'exit' or 'quit' to stop")
            print("="*60)
        await super().run(max_rounds=max_rounds)
