"""
ciris_engine/runtime/cli_runtime.py

CLI runtime for local testing and debugging.
"""
import asyncio
import logging
from typing import Optional, List
import uuid
from datetime import datetime, timezone

from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.runtime.base_runtime import CLIAdapter, IncomingMessage
from ciris_engine.ports import ActionSink
from ciris_engine.schemas.agent_core_schemas_v1 import Task
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine import persistence
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher

logger = logging.getLogger(__name__)


class CLIActionSink(ActionSink):
    """CLI implementation of ActionSink."""
    
    async def start(self) -> None:
        pass
        
    async def stop(self) -> None:
        pass
        
    async def send_message(self, channel_id: str, content: str) -> None:
        print(f"\n[CIRIS] {content}\n")
        
    async def run_tool(self, name: str, args: dict) -> None:
        print(f"[TOOL] {name}: {args}")
        

class InteractiveCLIAdapter(CLIAdapter):
    """Interactive CLI adapter that creates tasks from user input."""
    
    def __init__(self):
        super().__init__()
        self._should_stop = False
        
    async def fetch_inputs(self) -> List[IncomingMessage]:
        """Fetch input and create task directly."""
        if self._should_stop:
            return []
            
        try:
            # Use asyncio to read input without blocking
            line = await asyncio.get_event_loop().run_in_executor(
                None, input, "\n>>> "
            )
            
            if not line:
                return []
                
            if line.lower() in ["exit", "quit", "bye"]:
                self._should_stop = True
                print("Goodbye!")
                return []
                
            # Create a task directly
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
            
            persistence.add_task(task)
            logger.info(f"Created task {task_id} from CLI input")
            
            # Return empty list as we've already created the task
            return []
            
        except EOFError:
            self._should_stop = True
            return []
            

class CLIRuntime(CIRISRuntime):
    """CLI runtime for local testing."""
    
    def __init__(
        self,
        profile_name: str = "default",
        interactive: bool = True,
    ):
        cli_adapter = InteractiveCLIAdapter() if interactive else CLIAdapter()
        
        super().__init__(
            profile_name=profile_name,
            io_adapter=cli_adapter,
            startup_channel_id="cli",
        )
        
        self.action_sink = CLIActionSink()
        self.interactive = interactive
        
    async def _build_action_dispatcher(self, ponder_manager):
        """Build CLI-specific action dispatcher."""
        return build_action_dispatcher(
            audit_service=self.audit_service,
            ponder_manager=ponder_manager,
            action_sink=self.action_sink,
            memory_service=self.memory_service,
        )
        
    async def run(self, max_rounds: Optional[int] = None):
        """Run the CLI interface."""
        if self.interactive:
            print("\n" + "="*60)
            print("CIRIS Agent - Interactive CLI Mode")
            print(f"Profile: {self.profile_name}")
            print("Type 'exit' or 'quit' to stop")
            print("="*60)
            
        await super().run(max_rounds=max_rounds)