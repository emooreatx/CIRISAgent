import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.secrets.service import SecretsService

logger = logging.getLogger(__name__)

MessageT = TypeVar("MessageT", bound=BaseModel)

PASSIVE_CONTEXT_LIMIT = 10

class BaseObserver(Generic[MessageT], ABC):
    """Common functionality for message observers."""

    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        *,
        origin_service: str = "unknown",
    ) -> None:
        self.on_observe = on_observe
        self.memory_service = memory_service
        self.agent_id = agent_id
        self.multi_service_sink = multi_service_sink
        self.filter_service = filter_service
        self.secrets_service = secrets_service or SecretsService()
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

    async def _apply_message_filtering(self, msg: MessageT, adapter_type: str):
        from ciris_engine.schemas.filter_schemas_v1 import FilterResult, FilterPriority
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
            return filter_result
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
        try:
            processed_content, secret_refs = await self.secrets_service.process_incoming_text(
                msg.content,
                context_hint=f"{self.origin_service} message from {msg.author_name}",
                source_message_id=msg.message_id,
            )
            processed_msg = msg.model_copy(update={"content": processed_content})
            if secret_refs:
                processed_msg._detected_secrets = [
                    {
                        "uuid": ref.secret_uuid,
                        "context_hint": ref.context_hint,
                        "sensitivity": ref.sensitivity,
                    }
                    for ref in secret_refs
                ]
            return processed_msg
        except Exception as e:  # pragma: no cover - unlikely in tests
            logger.error("Error processing secrets in %s message %s: %s", self.origin_service, msg.message_id, e)
            return msg

    async def _get_recall_ids(self, msg: MessageT) -> set[str]:
        return {f"channel/{getattr(msg, 'channel_id', 'cli')}"}

    async def _recall_context(self, msg: MessageT) -> None:
        if not self.memory_service:
            return
        recall_ids = await self._get_recall_ids(msg)
        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]:
            if getattr(m, "author_id", None):
                recall_ids.add(f"user/{m.author_id}")
        from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
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
            if self.multi_service_sink:
                success = await self.multi_service_sink.send_message(
                    handler_name=self.__class__.__name__,
                    channel_id=getattr(msg, "channel_id", None),
                    content=f"[WA_FEEDBACK] {msg.content}",
                    metadata={
                        "message_type": "wa_feedback",
                        "original_message_id": msg.message_id,
                        "wa_user": msg.author_name,
                        "source": f"{self.origin_service}_observer",
                    },
                )
                if success:
                    logger.info(
                        "Enqueued WA feedback message %s from %s",
                        msg.message_id,
                        msg.author_name,
                    )
                else:
                    logger.warning("Failed to enqueue WA feedback message %s", msg.message_id)
            else:
                logger.warning("No multi_service_sink available for WA feedback routing")
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error adding WA feedback message %s to queue: %s", msg.message_id, e)

    async def _create_passive_observation_result(self, msg: MessageT) -> None:
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"Respond to message from @{msg.author_name} in #{msg.channel_id}: '{msg.content}'",
                status=TaskStatus.PENDING,
                priority=0,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": getattr(msg, "channel_id", None),
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": self.origin_service,
                    "observation_type": "passive",
                    "recent_messages": [
                        {
                            "id": m.message_id,
                            "content": m.content,
                            "author_id": m.author_id,
                            "author_name": m.author_name,
                            "channel_id": getattr(m, "channel_id", None),
                            "timestamp": getattr(m, "timestamp", "n/a"),
                        }
                        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]
                    ],
                },
            )
            persistence.add_task(task)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"User @{msg.author_name} said: {msg.content}",
                context=task.context,
            )
            persistence.add_thought(thought)
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error creating observation task: %s", e, exc_info=True)

    async def _create_priority_observation_result(self, msg: MessageT, filter_result: Any) -> None:
        try:
            from datetime import datetime, timezone
            import uuid
            from ciris_engine.schemas.agent_core_schemas_v1 import Task, Thought
            from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus
            from ciris_engine import persistence

            task_priority = 10 if getattr(filter_result.priority, "value", "") == "critical" else 5

            task = Task(
                task_id=str(uuid.uuid4()),
                description=f"PRIORITY: Respond to {filter_result.priority.value} message from @{msg.author_name}: '{msg.content}'",
                status=TaskStatus.PENDING,
                priority=task_priority,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                context={
                    "channel_id": getattr(msg, "channel_id", None),
                    "author_id": msg.author_id,
                    "author_name": msg.author_name,
                    "message_id": msg.message_id,
                    "origin_service": self.origin_service,
                    "observation_type": "priority",
                    "filter_priority": filter_result.priority.value,
                    "filter_reasoning": filter_result.reasoning,
                    "triggered_filters": filter_result.triggered_filters,
                    "filter_confidence": filter_result.confidence,
                    "filter_context": filter_result.context_hints,
                    "recent_messages": [
                        {
                            "id": m.message_id,
                            "content": m.content,
                            "author_id": m.author_id,
                            "author_name": m.author_name,
                            "channel_id": getattr(m, "channel_id", None),
                            "timestamp": getattr(m, "timestamp", "n/a"),
                        }
                        for m in self._history[-PASSIVE_CONTEXT_LIMIT:]
                    ],
                },
            )
            persistence.add_task(task)

            thought = Thought(
                thought_id=str(uuid.uuid4()),
                source_task_id=task.task_id,
                thought_type="observation",
                status=ThoughtStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                round_number=0,
                content=f"PRIORITY ({filter_result.priority.value}): User @{msg.author_name} said: {msg.content} | Filter: {filter_result.reasoning}",
                context=task.context,
            )
            persistence.add_thought(thought)
        except Exception as e:  # pragma: no cover - rarely hit in tests
            logger.error("Error creating priority observation task: %s", e, exc_info=True)

    async def get_recent_messages(self, limit: int = 20) -> List[Dict[str, Any]]:
        msgs = self._history[-limit:]
        return [
            {
                "id": m.message_id,
                "content": m.content,
                "author_id": m.author_id,
                "timestamp": getattr(m, "timestamp", "n/a"),
            }
            for m in msgs
        ]
