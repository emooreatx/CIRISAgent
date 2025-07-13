#!/usr/bin/env python3
"""
Stage 2: Remove unused variables identified by flake8.
Only removes variables that are truly unused (not used for side effects).
"""
import os
import re


# List of unused variables to remove
# Format: (filepath, line_number, variable_name)
UNUSED_VARIABLES = [
    ("ciris_engine/logic/adapters/api/routes/audit.py", 237, "_verification_report"),
    ("ciris_engine/logic/adapters/api/routes/auth.py", 56, "config_service"),
    ("ciris_engine/logic/adapters/api/routes/config.py", 169, "_errors"),
    ("ciris_engine/logic/adapters/api/routes/config.py", 170, "_warnings"),
    ("ciris_engine/logic/adapters/api/routes/emergency.py", 99, "e"),
    ("ciris_engine/logic/adapters/api/routes/memory.py", 248, "_total"),
    ("ciris_engine/logic/adapters/api/routes/memory.py", 342, "_query_body"),
    ("ciris_engine/logic/adapters/api/routes/system.py", 959, "tool_services"),
    ("ciris_engine/logic/adapters/api/routes/telemetry_metrics.py", 30, "hour_ago"),
    ("ciris_engine/logic/adapters/api/routes/wa.py", 356, "wa_service"),
    ("ciris_engine/logic/adapters/base_observer.py", 287, "_minimal_snapshot"),
    ("ciris_engine/logic/adapters/base_observer.py", 326, "_timestamp"),
    ("ciris_engine/logic/adapters/cli/cli_tools.py", 79, "_execution_time"),
    ("ciris_engine/logic/adapters/discord/discord_adapter.py", 176, "_result"),
    ("ciris_engine/logic/adapters/discord/discord_adapter.py", 978, "_deferral_id"),
    ("ciris_engine/logic/adapters/discord/discord_adapter.py", 1032, "_result"),
    ("ciris_engine/logic/adapters/discord/discord_observer.py", 242, "_thought_id_match"),
    ("ciris_engine/logic/adapters/discord/discord_rate_limiter.py", 144, "_bucket_id"),
    ("ciris_engine/logic/adapters/discord/discord_tool_handler.py", 152, "response_data"),
    ("ciris_engine/logic/conscience/core.py", 176, "ts"),
    ("ciris_engine/logic/conscience/core.py", 271, "ts"),
    ("ciris_engine/logic/conscience/core.py", 376, "ts"),
    ("ciris_engine/logic/conscience/core.py", 464, "ts"),
    ("ciris_engine/logic/conscience/thought_depth_guardrail.py", 176, "_defer_action"),
    ("ciris_engine/logic/context/system_snapshot.py", 324, "bus_manager"),
    ("ciris_engine/logic/dma/action_selection/action_instruction_generator.py", 319, "_description"),
    ("ciris_engine/logic/dma/action_selection/context_builder.py", 187, "_all_tools"),
    ("ciris_engine/logic/dma/pdma.py", 108, "_resource_usage"),
    ("ciris_engine/logic/handlers/control/defer_handler.py", 135, "action_performed_successfully"),
    ("ciris_engine/logic/handlers/control/defer_handler.py", 163, "_action_performed_successfully"),
]


def remove_unused_variable(filepath, line_num, var_name):
    """Remove or modify a line with an unused variable."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return False
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Adjust for 0-based indexing
    idx = line_num - 1
    
    if idx >= len(lines):
        print(f"Line {line_num} out of range in {filepath}")
        return False
    
    line = lines[idx]
    
    # Handle different patterns
    if f"{var_name} =" in line:
        # Check if it's a simple assignment
        if " = " in line:
            # Extract the right-hand side
            parts = line.split(" = ", 1)
            if len(parts) == 2:
                rhs = parts[1].strip()
                # If RHS might have side effects, keep it
                if any(keyword in rhs for keyword in ["(", "await", "."]):
                    # Convert to expression statement
                    new_line = " " * (len(line) - len(line.lstrip())) + rhs
                    if not new_line.endswith("\n"):
                        new_line += "\n"
                    lines[idx] = new_line
                    print(f"  Modified: {var_name} = {rhs} -> {rhs}")
                else:
                    # Safe to remove entirely
                    lines.pop(idx)
                    print(f"  Removed: {line.strip()}")
            else:
                print(f"  Skipped complex assignment: {line.strip()}")
                return False
        else:
            print(f"  Skipped: {line.strip()}")
            return False
    else:
        print(f"  Could not find variable {var_name} on line {line_num}")
        return False
    
    # Write back
    with open(filepath, 'w') as f:
        f.writelines(lines)
    
    return True


def main():
    """Remove all unused variables."""
    print("Stage 2: Removing unused variables\n")
    
    removed_count = 0
    
    for filepath, line_num, var_name in UNUSED_VARIABLES:
        print(f"Processing {filepath}:{line_num} ({var_name}):")
        if remove_unused_variable(filepath, line_num, var_name):
            removed_count += 1
        print()
    
    print(f"\nTotal variables processed: {removed_count}")
    print("\nNext steps:")
    print("1. Run: pytest")
    print("2. Run: mypy ciris_engine/")
    print("3. If all pass, commit changes")


if __name__ == "__main__":
    main()