import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Generic, List, Optional, Set, TypeVar, cast, Any

from pydantic import BaseModel

from ciris_engine.schemas.runtime.enums import ThoughtType
from ciris_engine.schemas.runtime.models import TaskContext, ThoughtContext as ThoughtModelContext
from ciris_engine.logic.utils.channel_utils import create_channel_context
from ciris_engine.schemas.services.filters_core import FilterResult, FilterPriority

from ciris_engine.logic.buses import BusManager
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MessageT = TypeVar("MessageT", bound=BaseModel)

PASSIVE_CONTEXT_LIMIT = 10

class BaseObserver(Generic[MessageT], ABC):
    """Common functionality for message observers."""

    def __init__(
        self,
        on_observe: Callable[[dict], Awaitable[None]],
        bus_manager: Optional[BusManager] = None,
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        time_service: Optional[TimeServiceProtocol] = None,
        auth_service: Optional[Any] = None,
        observer_wa_id: Optional[str] = None,
        *,
        origin_service: str = "unknown",
    ) -> None:
        self.on_observe = on_observe
        self.bus_manager = bus_manager
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.filter_service = filter_service
        self.secrets_service = secrets_service
        self.time_service = time_service
        self.auth_service = auth_service
        self.observer_wa_id = observer_wa_id
        self.origin_service = origin_service
        self._history: List[MessageT] = []

    @abstractmethod
    async def start(self) -> None:  # pragma: no cover - implemented by subclasses
        pass

    @abstractmethod
    async def stop(self) -> None:  # pragma: no cover - implemented by subclasses
        pass

    def _is_agent_message(self, msg: MessageT) -> bool:
        if self.agent_id and getattr(msg, "author_id", None) == self.agent_id:
            return True
        return getattr(msg, "is_bot", False)

    async def _apply_message_filtering(self, msg: MessageT, adapter_type: str) -> FilterResult:
        if not self.filter_service:
            return FilterResult(
                message_id=getattr(msg, "message_id", "unknown"),
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning="No filter service available - processing normally",
            )
        try:
            filter_result = await self.filter_service.filter_message(
                message=msg,
                adapter_type=adapter_type,
            )
            if filter_result.triggered_filters:
                logger.debug(
                    "Message %s triggered filters: %s",
                    getattr(msg, "message_id", "unknown"),
                    filter_result.triggered_filters,
                )
            return cast(FilterResult, filter_result)
        except Exception as e:  # pragma: no cover - unlikely in tests
            logger.error("Error applying filter to message %s: %s", getattr(msg, "message_id", "unknown"), e)
            return FilterResult(
                message_id=getattr(msg, "message_id", "unknown"),
                priority=FilterPriority.MEDIUM,
                triggered_filters=[],
                should_process=True,
                reasoning=f"Filter error, processing normally: {e}",
            )

    async def _process_message_secrets(self, msg: MessageT) -> MessageT:
        if not self.secrets_service:
            logger.error(f"CRITICAL: secrets_service is None in {self.origin_service} observer! Cannot process secrets.")
            raise RuntimeError("SecretsService is required but not available")
        try:
            processed_content, secret_refs = await self.secrets_service.process_incoming_text(
                msg.content,  # type: ignore[attr-defined]
                msg.message_id,  # type: ignore[attr-defined]
            )
            processed_msg = msg.model_copy(update={"content": processed_content})
            if secret_refs:
                processed_msg._detected_secrets = [  # type: ignore[attr-defined]
                    {
                        "uuid": ref.secret_uuid,  # type: ignore[attr-defined]
                        "context_hint": ref.context_hint,
                        "sensitivity": ref.sensitivity,
                    }
                    for ref in secret_refs
                ]
            return processed_msg
        except Exception as e:  # pragma: no cover - unlikely in tests
            logger.error("Error processing secrets in %s message %s: %s", self.origin_service, msg.message_id, e)  # type: ignore[attr-defined]
            return msg

    async def _get_recall_ids(self, msg: MessageT) -> Set[str]:
        return {f"channel/{getattr(msg, 'channel_id', 'cli')}"}

    async def _recall_context(self, msg: MessageT) -> None:
        if not self.memory_service:
            return
        recall_ids = await self._get_recall_ids(msg)
        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]:
            if getattr(m, "author_id", None):
                recall_ids.add(f"user/{m.author_id}")  # type: ignore[attr-defined]
        from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
        for rid in recall_ids:
            for scope in (
                GraphScope.IDENTITY,
                GraphScope.ENVIRONMENT,
                GraphScope.LOCAL,
            ):
                try:
                    if rid.startswith("channel/"):
                        node_type = NodeType.CHANNEL
                    elif rid.startswith("user/"):
                        node_type = NodeType.USER
                    else:
                        node_type = NodeType.CONCEPT
                    node = GraphNode(id=rid, type=node_type, scope=scope)
                    await self.memory_service.recall(node)
                except Exception:
                    continue

    async def _add_to_feedback_queue(self, msg: MessageT) -> None:
        try:
            if self.bus_manager:
                success = await self.bus_manager.communication.send_message(
                    handler_name=self.__class__.__name__,
                    channel_id=str(getattr(msg, "channel_id", "")) or "unknown",
                    content=f"[WA_FEEDBACK] {msg.content}",  # type: ignore[attr-defined]
                    metadata={
                        "message_type": "wa_feedback",
                        "original_message_id": msg.message_id,  # type: ignore[attr-defined]
                        "wa_user": msg.author_name,  # type: ignore[attr-defined]
                        "source": f"{self.origin_service}_observer",
                    },
                )
                if success:
                    logger.info(
                        "Enqueued WA feedback message %s from %s",
                        msg.message_id,  # type: ignore[attr-defined]
                        msg.author_name,  # type: ignore[attr-defined]
                    )
                else:
                    logger.warning("Failed to enqueue WA feedback message %s", msg.message_id)  # type: ignore[attr-defined]
            else:
                logger.warning("No bus_manager available for WA feedback routing")
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error adding WA feedback message %s to queue: %s", msg.message_id, e)  # type: ignore[attr-defined]

    async def _sign_and_add_task(self, task: Any) -> None:
        """Sign the task with observer's WA certificate before adding."""
        # If auth service and observer WA ID are available, sign the task
        if self.auth_service and self.observer_wa_id:
            try:
                signature, signed_at = await self.auth_service.sign_task(task, self.observer_wa_id)
                task.signed_by = self.observer_wa_id
                task.signature = signature
                task.signed_at = signed_at
                logger.debug(f"Signed observer task {task.task_id} with observer WA {self.observer_wa_id}")
            except Exception as e:
                logger.error(f"Failed to sign observer task: {e}")
                # Continue without signature
        
        # Import persistence here to avoid circular import
        from ciris_engine.logic import persistence
        persistence.add_task(task)
    
    async def _create_passive_observation_result(self, msg: MessageT) -> None:
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.runtime.models import Task, Thought
            from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
            from ciris_engine.schemas.runtime.system_context import SystemSnapshot, ChannelContext
            from ciris_engine.logic import persistence

            # Create minimal system snapshot for passive observation
            channel_context = ChannelContext(
                channel_id=getattr(msg, "channel_id", "system"),
                channel_name=getattr(msg, "channel_name", f"Channel {getattr(msg, 'channel_id', 'system')}"),
                channel_type="text",
                is_private=False,
                created_at=self.time_service.now(),
                allowed_actions=["send_messages", "read_messages"]
            )
            
            minimal_snapshot = SystemSnapshot(
                channel_context=channel_context,
                agent_identity={
                    "agent_id": self.agent_id or "ciris",
                    "purpose": "Process and respond to messages"
                }
            )

            # Build message history context
            history_context = []
            for hist_msg in self._history[-PASSIVE_CONTEXT_LIMIT:]:
                history_context.append({
                    "author": getattr(hist_msg, "author_name", "Unknown"),
                    "content": getattr(hist_msg, "content", ""),
                    "timestamp": getattr(hist_msg, "timestamp", "")
                })

            task = Task(
                task_id=str(uuid.uuid4()),
                channel_id=getattr(msg, "channel_id", "system"),
                description=f"Respond to message from @{msg.author_name} (ID: {msg.author_id}) in #{msg.channel_id}: '{msg.content}'",  # type: ignore[attr-defined]
                status=TaskStatus.PENDING,
                priority=0,
                created_at=self.time_service.now_iso(),
                updated_at=self.time_service.now_iso(),
                context=TaskContext(
                    channel_id=getattr(msg, "channel_id", None),
                    user_id=msg.author_id,  # type: ignore[attr-defined]
                    correlation_id=msg.message_id,  # type: ignore[attr-defined]
                    parent_task_id=None
                ),
            )
            
            await self._sign_and_add_task(task)

            # Build conversation context for thought
            conversation_lines = ["=== CONVERSATION HISTORY (Last 10 messages) ==="]
            for i, hist_msg in enumerate(self._history[-PASSIVE_CONTEXT_LIMIT:], 1):
                author = getattr(hist_msg, "author_name", "Unknown")
                author_id = getattr(hist_msg, "author_id", "unknown")
                content = getattr(hist_msg, "content", "")
                timestamp = getattr(hist_msg, "timestamp", "")
                conversation_lines.append(f"{i}. @{author} (ID: {author_id}): {content}")
            
            conversation_lines.append("\n=== CURRENT MESSAGE TO RESPOND TO ===")
            conversation_lines.append(f"@{msg.author_name} (ID: {msg.author_id}): {msg.content}")  # type: ignore[attr-defined]
            conversation_lines.append("=" * 40)
            
            thought_content = "\n".join(conversation_lines)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type=ThoughtType.OBSERVATION,
                status=ThoughtStatus.PENDING,
                created_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                updated_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=thought_content,
                context=ThoughtModelContext(
                    task_id=task.task_id,
                    channel_id=getattr(msg, "channel_id", None),
                    round_number=0,
                    depth=0,
                    parent_thought_id=None,
                    correlation_id=msg.message_id  # type: ignore[attr-defined]
                ),
            )
            
            persistence.add_thought(thought)
            logger.info(f"Created task {task.task_id} for: {getattr(msg, 'content', 'unknown')[:50]}...")
            
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error creating observation task: %s", e, exc_info=True)

    async def _create_priority_observation_result(self, msg: MessageT, filter_result: Any) -> None:
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.runtime.models import Task, Thought
            from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
            from ciris_engine.logic import persistence

            task_priority = 10 if getattr(filter_result.priority, "value", "") == "critical" else 5

            task = Task(
                task_id=str(uuid.uuid4()),
                channel_id=getattr(msg, "channel_id", "system"),
                description=f"PRIORITY: Respond to {filter_result.priority.value} message from @{msg.author_name} (ID: {msg.author_id}): '{msg.content}'",  # type: ignore[attr-defined]
                status=TaskStatus.PENDING,
                priority=task_priority,
                created_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                updated_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                context=TaskContext(
                    channel_id=getattr(msg, "channel_id", None),
                    user_id=msg.author_id,  # type: ignore[attr-defined]
                    correlation_id=msg.message_id,  # type: ignore[attr-defined]
                    parent_task_id=None
                ),
            )
            await self._sign_and_add_task(task)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type=ThoughtType.OBSERVATION,
                status=ThoughtStatus.PENDING,
                created_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                updated_at=self.time_service.now_iso() if self.time_service else datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"PRIORITY ({filter_result.priority.value}): User @{msg.author_name} (ID: {msg.author_id}) said: {msg.content} | Filter: {filter_result.reasoning}",  # type: ignore[attr-defined]
                context=ThoughtModelContext(
                    task_id=task.task_id,
                    channel_id=getattr(msg, "channel_id", None),
                    round_number=0,
                    depth=0,
                    parent_thought_id=None,
                    correlation_id=msg.message_id  # type: ignore[attr-defined]
                ),
            )
            persistence.add_thought(thought)
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error creating priority observation task: %s", e, exc_info=True)

    async def get_recent_messages(self, limit: int = 20) -> List[dict]:
        msgs = self._history[-limit:]
        return [
            {
                "id": m.message_id,  # type: ignore[attr-defined]
                "content": m.content,  # type: ignore[attr-defined]
                "author_id": m.author_id,  # type: ignore[attr-defined]
                "timestamp": getattr(m, "timestamp", "n/a"),
            }
            for m in msgs
        ]
