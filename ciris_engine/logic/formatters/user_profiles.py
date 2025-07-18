
from typing import List, Optional, Any

def format_user_profiles(profiles: Optional[dict[str, Any]]) -> str:
    """Copy of format_user_profiles_for_prompt with new module path."""
    # *** copied logic – do not modify yet ***
    if not profiles or not isinstance(profiles, dict):
        return ""

    profile_parts: List[str] = []
    for user_key, profile_data in profiles.items():
        if isinstance(profile_data, dict):
            display_name = profile_data.get('name') or profile_data.get('nick') or user_key
            profile_summary = f"User '{user_key}': Name/Nickname: '{display_name}'"

            interest = profile_data.get('interest')
            if interest:
                profile_summary += f", Interest: '{str(interest)}'"

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
