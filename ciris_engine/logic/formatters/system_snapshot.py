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
    
    # CRITICAL: Check for resource alerts FIRST
    if hasattr(system_snapshot, 'resource_alerts') and system_snapshot.resource_alerts:
        lines.append("🚨🚨🚨 CRITICAL RESOURCE ALERTS 🚨🚨🚨")
        for alert in system_snapshot.resource_alerts:
            lines.append(alert)
        lines.append("🚨🚨🚨 END CRITICAL ALERTS 🚨🚨🚨")
        lines.append("")  # Empty line for emphasis

    # System counts if available
    if hasattr(system_snapshot, 'system_counts') and system_snapshot.system_counts:
        counts = system_snapshot.system_counts
        if 'pending_tasks' in counts:
            lines.append(f"Pending Tasks: {counts['pending_tasks']}")
        if 'pending_thoughts' in counts:
            lines.append(f"Pending Thoughts: {counts['pending_thoughts']}")
        if 'total_tasks' in counts:
            lines.append(f"Total Tasks: {counts['total_tasks']}")
        if 'total_thoughts' in counts:
            lines.append(f"Total Thoughts: {counts['total_thoughts']}")

    # Legacy fields for backward compatibility
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
