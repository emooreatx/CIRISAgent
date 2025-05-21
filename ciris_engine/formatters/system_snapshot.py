from typing import Dict


def format_system_snapshot(system_snapshot: Dict) -> str:
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

    # Display order / whitelist
    fields = [
        ("pending_tasks", "Pending Tasks"),
        ("active_thoughts", "Active Thoughts"),
        ("completed_tasks", "Completed Tasks"),
        ("recent_errors", "Recent Errors"),
        # ↳ add more tuples as needed
    ]

    for key, label in fields:
        if key in system_snapshot:
            val = system_snapshot[key]
            lines.append(f"{label}: {val}")

    return "\n".join(lines)
