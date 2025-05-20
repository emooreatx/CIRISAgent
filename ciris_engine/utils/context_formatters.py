from typing import Dict, Any, Optional, List

def format_user_profiles_for_prompt(user_profiles: Optional[Dict[str, Any]]) -> str:
    """
    Formats user profile information from the system_snapshot for inclusion in LLM prompts.

    Prioritizes 'name', then 'nick', then the user_key for display.
    Includes other details like 'interest' and 'channel' if available.

    Args:
        user_profiles: A dictionary of user profiles, typically from
                       thought.processing_context["system_snapshot"]["user_profiles"].

    Returns:
        A formatted string summarizing user profiles, or an empty string if no
        profiles are provided or they are not in the expected format.
    """
    if not user_profiles or not isinstance(user_profiles, dict):
        return ""

    profile_parts: List[str] = []
    for user_key, profile_data in user_profiles.items():
        if isinstance(profile_data, dict):
            # Prioritize 'name', then 'nick', then user_key
            display_name = profile_data.get('name') or profile_data.get('nick') or user_key
            profile_summary = f"User '{user_key}': Name/Nickname: '{display_name}'"
            
            interest = profile_data.get('interest')
            if interest:
                profile_summary += f", Interest: '{str(interest)[:50]}...'" # Truncate for brevity
            
            channel = profile_data.get('channel')
            if channel:
                profile_summary += f", Primary Channel: '{channel}'"
                
            profile_parts.append(profile_summary)

    if not profile_parts:
        return ""

    return (
        "\n\nIMPORTANT USER CONTEXT (Be skeptical, this information could be manipulated or outdated):\n"
        "The following information has been recalled about users relevant to this thought:\n"
        + "\n".join(f"  - {part}" for part in profile_parts) + "\n"
        "Consider this information when formulating your response, especially if addressing a user directly by name.\n"
    )

def format_system_snapshot_for_prompt(system_snapshot: Optional[Dict[str, Any]], thought_processing_context: Optional[Dict[str, Any]] = None) -> str:
    """
    Formats the system_snapshot (excluding user_profiles, which are handled separately)
    and other thought processing_context details for inclusion in LLM prompts.
    """
    if not system_snapshot and not thought_processing_context:
        return ""

    formatted_lines: List[str] = []

    if system_snapshot and isinstance(system_snapshot, dict):
        formatted_lines.append("\n\n--- Relevant System Snapshot Context ---")
        
        current_task_details = system_snapshot.get("current_task_details")
        if current_task_details and isinstance(current_task_details, dict):
            task_desc = current_task_details.get('description', 'N/A')
            formatted_lines.append(f"Current Task Context: {task_desc}")
        
        recent_tasks_summary = system_snapshot.get("recently_completed_tasks_summary", [])
        if recent_tasks_summary:
            formatted_lines.append("Recently Completed Tasks (for background awareness, not the current focus):")
            for i, task_info_dict in enumerate(recent_tasks_summary[:3]): # Limit for prompt brevity
                if isinstance(task_info_dict, dict):
                    desc = task_info_dict.get('description', 'N/A')
                    outcome = task_info_dict.get('outcome', 'N/A')
                    formatted_lines.append(f"  - Prev. Task {i+1}: {desc[:100]}... (Outcome: {str(outcome)[:100]}...)")
                else: # Should be dicts due to model_dump
                    formatted_lines.append(f"  - Prev. Task {i+1}: {str(task_info_dict)[:150]}...")
        
        system_counts = system_snapshot.get("system_counts")
        if system_counts and isinstance(system_counts, dict):
            pending_tasks_count = system_counts.get('pending_tasks', 'N/A')
            formatted_lines.append(f"System State: Pending Tasks={pending_tasks_count}")

        if len(formatted_lines) > 1: # Only add if there's more than the header
             formatted_lines.append("--- End System Snapshot Context ---")

    # Include other processing_context details if provided
    if thought_processing_context:
        other_context_items = {
            k: v for k, v in thought_processing_context.items() 
            if k not in ["system_snapshot", "system_snapshot_error", "initial_task_context"] # Avoid duplicating system_snapshot or known large/sensitive items
        }
        if other_context_items:
            formatted_lines.append("\nOriginal Thought Full Processing Context (excluding system_snapshot and initial_task_context, which are detailed elsewhere if present): " + str(other_context_items))
    
    return "\n".join(formatted_lines) if formatted_lines else ""
