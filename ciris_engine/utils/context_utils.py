from typing import Any, Dict, Optional

def build_dispatch_context(item, thought, task, extra_context=None):
    context = item.initial_context.copy() if getattr(item, "initial_context", None) else {}
    context["thought_id"] = item.thought_id
    context["source_task_id"] = item.source_task_id

    if task and getattr(task, "context", None):
        for key in ["origin_service", "author_name", "author_id", "channel_id"]:
            if key not in context and key in task.context:
                context[key] = task.context[key]
        # Ensure channel_id is also present in the thought context for downstream consumers (e.g., guardrails)
        if "channel_id" in task.context and (not hasattr(thought, 'context') or not thought.context or "channel_id" not in thought.context):
            if not hasattr(thought, 'context') or thought.context is None:
                thought.context = {}
            thought.context["channel_id"] = task.context["channel_id"]

    if extra_context:
        context.update(extra_context)
    return context