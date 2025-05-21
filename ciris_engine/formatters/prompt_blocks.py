"""Prompt block formatting utilities."""
from ciris_engine.utils.task_formatters import format_task_context
from .system_snapshot import format_system_snapshot
from .user_profiles import format_user_profiles


def format_parent_task_chain(parent_tasks):
    """Formats the parent task chain, root first, for the prompt."""
    if not parent_tasks:
        return "=== Parent Task Chain ===\nNone"
    lines = ["=== Parent Task Chain ==="]
    for i, pt in enumerate(parent_tasks):
        if i == 0:
            prefix = "Root Task"
        elif i == len(parent_tasks) - 1:
            prefix = "Direct Parent"
        else:
            prefix = f"Parent {i}"
        desc = pt.get("description", "")[:150]
        tid = pt.get("task_id", "N/A")
        lines.append(f"{prefix}: {desc} (Task ID: {tid})")
    return "\n".join(lines)


def format_thoughts_chain(thoughts):
    """Formats all thoughts under consideration, active thought last."""
    if not thoughts:
        return "=== Thoughts Under Consideration ===\nNone"
    lines = ["=== Thoughts Under Consideration ==="]
    for i, thought in enumerate(thoughts):
        is_active = i == len(thoughts) - 1
        label = "Active Thought" if is_active else f"Thought {i+1}"
        content = thought.get("content", "")[:500]
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def format_system_prompt_blocks(
    task_history_block,
    system_snapshot_block,
    user_profiles_block,
    escalation_guidance_block=None,
    system_guidance_block=None,
):
    """Assemble the system prompt in canonical CIRIS order."""
    blocks = [task_history_block]
    if system_guidance_block:
        blocks.append(system_guidance_block)
    if escalation_guidance_block:
        blocks.append(escalation_guidance_block)
    blocks.extend([system_snapshot_block, user_profiles_block])
    return "\n\n".join(filter(None, blocks)).strip()


def format_user_prompt_blocks(
    parent_tasks_block,
    thoughts_chain_block,
    schema_block=None,
):
    """Assemble the user prompt in canonical CIRIS order."""
    blocks = [parent_tasks_block, thoughts_chain_block]
    if schema_block:
        blocks.append(schema_block)
    return "\n\n".join(filter(None, blocks)).strip()


__all__ = [
    "format_task_context",
    "format_system_snapshot",
    "format_user_profiles",
    "format_parent_task_chain",
    "format_thoughts_chain",
    "format_system_prompt_blocks",
    "format_user_prompt_blocks",
]
