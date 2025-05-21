"""Prompt engineering utilities for summarizing task context."""

from typing import List, Dict, Optional


def format_task_context(current_task: Dict[str, str],
                         recent_actions: List[Dict[str, str]],
                         completed_tasks: Optional[List[Dict[str, str]]] = None,
                         max_actions: int = 5) -> str:
    """Return a formatted summary block for LLM prompts.

    Parameters
    ----------
    current_task : Dict[str, str]
        Mapping containing ``description``, ``task_id`` and optional ``status``
        and ``priority``.
    recent_actions : List[Dict[str, str]]
        Sequence of recent actions with ``description``, ``outcome`` and
        ``updated_at`` fields.
    completed_tasks : List[Dict[str, str]], optional
        Optional list of completed tasks for additional context. Only the first
        item is included.
    max_actions : int, default 5
        Maximum number of actions to include.

    Returns
    -------
    str
        A human-readable block describing the task context.
    """

    if not isinstance(current_task, dict):
        raise TypeError("current_task must be a dict")

    out_lines: List[str] = ["=== Current Task ==="]
    cur_desc = str(current_task.get("description", ""))[:200]
    task_id = current_task.get("task_id", "N/A")
    status = current_task.get("status", "N/A")
    priority = current_task.get("priority", "N/A")
    out_lines.append(f"{cur_desc} (Task ID: {task_id}, Status: {status}, Priority: {priority})")

    if recent_actions:
        out_lines.append("\n=== Recent Actions ===")
        for idx, act in enumerate(recent_actions[:max_actions], 1):
            if not isinstance(act, dict):
                continue
            desc = str(act.get("description", ""))[:120]
            outcome = str(act.get("outcome", ""))[:100]
            upd = act.get("updated_at", "N/A")
            out_lines.append(f"{idx}. {desc} | Outcome: {outcome} (updated: {upd})")

    if completed_tasks:
        last = completed_tasks[0]
        if isinstance(last, dict):
            desc = str(last.get("description", ""))[:120]
            outcome = str(last.get("outcome", ""))[:100]
            upd = last.get("updated_at", "N/A")
            out_lines.append(f"\n=== Last Completed Task ===\n{desc} | Outcome: {outcome} (completed: {upd})")

    return "\n".join(out_lines)

