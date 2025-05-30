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
    async def send_message(self, channel_id: str, content: str) -> None:
        print(f"\n[CIRIS] {content}\n")
    async def run_tool(self, name: str, args: dict) -> None:
        print(f"[TOOL] {name}: {args}")

class InteractiveCLIAdapter(CLIAdapter):
    def __init__(self):
        super().__init__()
        self._should_stop = False

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
            task_id = f"cli_{uuid.uuid4().hex[:8]}"
            now = datetime.now(timezone.utc).isoformat()
            task = Task(
                task_id=task_id,
                description=line,
                status=TaskStatus.PENDING,
                priority=1,
                created_at=now,
                updated_at=now,
                context={
                    "origin_service": "cli",
                    "author_id": "local_user",
                    "author_name": "User",
                    "channel_id": "cli",
                    "content": line,
                }
            )
            # Ensure the database is initialized before adding the task
            persistence.initialize_database()
            persistence.add_task(task)
            logger.info(f"Created task {task_id} from CLI input")
            return []
        except EOFError:
            self._should_stop = True
            return []

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
