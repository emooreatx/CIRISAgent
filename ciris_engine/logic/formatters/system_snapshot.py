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

    # Telemetry/Resource Usage Summary
    if hasattr(system_snapshot, 'telemetry_summary') and system_snapshot.telemetry_summary:
        telemetry = system_snapshot.telemetry_summary
        lines.append("")
        lines.append("=== Resource Usage ===")
        
        # Current hour usage
        if telemetry.tokens_per_hour > 0:
            lines.append(f"Tokens (Current Hour): {int(telemetry.tokens_per_hour):,} tokens, ${telemetry.cost_per_hour_cents/100:.2f}, {telemetry.carbon_per_hour_grams:.1f}g CO2")
        
        # 24h usage
        if telemetry.messages_processed_24h > 0 or telemetry.thoughts_processed_24h > 0:
            # Calculate 24h totals from hourly rates
            tokens_24h = int(telemetry.tokens_per_hour * 24)
            cost_24h = telemetry.cost_per_hour_cents * 24 / 100
            carbon_24h = telemetry.carbon_per_hour_grams * 24
            
            lines.append(f"Tokens (Past 24h): {tokens_24h:,} tokens, ${cost_24h:.2f}, {carbon_24h:.1f}g CO2")
        
        # Activity metrics
        if telemetry.messages_processed_24h > 0:
            lines.append(f"Messages Processed: {telemetry.messages_current_hour} (current hour), {telemetry.messages_processed_24h} (24h)")
        if telemetry.thoughts_processed_24h > 0:
            lines.append(f"Thoughts Processed: {telemetry.thoughts_current_hour} (current hour), {telemetry.thoughts_processed_24h} (24h)")
        
        # Error rate if significant
        if telemetry.error_rate_percent > 1.0:
            lines.append(f"⚠️ Error Rate: {telemetry.error_rate_percent:.1f}% ({telemetry.errors_24h} errors in 24h)")
        
        # Service breakdown if available
        if telemetry.service_calls:
            lines.append("")
            lines.append("Service Usage:")
            for service, count in sorted(telemetry.service_calls.items(), key=lambda x: x[1], reverse=True)[:5]:
                lines.append(f"  - {service}: {count} calls")
    
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
