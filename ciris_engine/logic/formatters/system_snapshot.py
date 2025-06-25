from ciris_engine.schemas.runtime.system_context import SystemSnapshot

def format_system_snapshot(system_snapshot: SystemSnapshot) -> str:
    """Summarize core system counters for LLM prompt context.

    Parameters
    ----------
    system_snapshot : dict
        Mapping of counters such as ``pending_tasks`` and ``active_thoughts``.

    Returns
    -------
    str
        Compact block ready to append after task context.
    """

    lines = ["=== System Snapshot ==="]

    fields = [
        ("active_tasks", "Active Tasks"),
        ("active_thoughts", "Active Thoughts"),
        ("queue_depth", "Queue Depth"),
        ("error_rate", "Error Rate"),
    ]

    for key, label in fields:
        if hasattr(system_snapshot, key):
            val = getattr(system_snapshot, key)
            if val is not None:
                lines.append(f"{label}: {val}")

    return "\n".join(lines)
