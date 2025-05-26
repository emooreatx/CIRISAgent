"""Simplified agent processor for pre-alpha refactoring."""

import asyncio
from typing import Dict, Optional
from datetime import datetime, timezone

from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus

from .states import AgentState
from .coordinator import Coordinator


class Processor:
    """Minimal in-memory processor managing tasks and thoughts."""

    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
        self.tasks: Dict[str, Task] = {}
        self.thoughts: Dict[str, Thought] = {}
        self.current_state: Optional[AgentState] = None

    def set_state(self, state: AgentState) -> None:
        """Create or replace the root task for the given state."""
        now = datetime.now(timezone.utc).isoformat()
        self.current_state = state
        root_task = Task(
            task_id=state.value,
            description=f"{state.value} root",
            status=TaskStatus.ACTIVE,
            priority=0,
            created_at=now,
            updated_at=now,
            parent_task_id=None,
            context={},
        )
        self.tasks[state.value] = root_task

    def add_thought(self, thought: Thought) -> None:
        """Add a thought to the processing pool."""
        self.thoughts[thought.thought_id] = thought

    async def process_round(self) -> None:
        """Process all pending thoughts once."""
        pending = [t for t in self.thoughts.values() if t.status == ThoughtStatus.PENDING]
        for thought in pending:
            thought.status = ThoughtStatus.PROCESSING
            action = await self.coordinator.process_thought(thought)
            if self.coordinator.last_pdma_result is not None:
                thought.context["pdma_result"] = self.coordinator.last_pdma_result.model_dump()
            thought.final_action = {"type": action.value}
            thought.status = ThoughtStatus.COMPLETED

    async def run(self) -> None:
        """Continuously process rounds until cancelled."""
        while True:
            await self.process_round()
            await asyncio.sleep(0.1)
