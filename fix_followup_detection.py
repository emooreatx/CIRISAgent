#!/usr/bin/env python3
"""
Explain the mock LLM follow-up detection issue and fix.

PROBLEM:
1. When speak_handler creates a follow-up thought, it includes this content:
   "CIRIS_FOLLOW_UP_THOUGHT: YOU Spoke, as a result of your action: '{params.content}' ..."
   
2. This content becomes the thought's content and is passed to the mock LLM

3. The mock LLM extracts context from messages and looks for patterns

4. BUT: The detection is failing because the context extraction is adding many items,
   and the "CIRIS_FOLLOW_UP_THOUGHT" pattern is getting buried or not properly detected

CURRENT DETECTION CODE:
    # Check if this is a follow-up thought using the mock LLM context pattern
    is_followup = any("MOCK_LLM_CONTEXT" in str(item) and "follow-up thought" in str(item) for item in context)
    
    # Also check for legacy patterns for backwards compatibility
    if not is_followup:
        is_followup = any("action_performed:" in item or "FOLLOW_UP" in str(item) or "followup" in str(item).lower() or "CIRIS_FOLLOW_UP_THOUGHT" in str(item) for item in context)

THE ISSUE:
The context items include things like:
- echo_content:Hello from test!\\'. The next\\n ...
- echo_channel:test_speak_channel
- CIRIS_FOLLOW_UP_THOUGHT
- etc.

But the detection looks for "CIRIS_FOLLOW_UP_THOUGHT" in str(item), and the items are already strings!

SOLUTION:
The fix is to check if any context item IS EXACTLY "CIRIS_FOLLOW_UP_THOUGHT" or contains it as a substring.
"""

print(__doc__)

# Show the fix
print("\nFIX TO APPLY:")
print("In /home/emoore/CIRISAgent/tests/adapters/mock_llm/responses_action_selection.py")
print("Replace the follow-up detection logic with:")
print("""
    else:
        # Check if this is a follow-up thought
        is_followup = False
        
        # Check for CIRIS_FOLLOW_UP_THOUGHT marker in context items
        for item in context:
            if "CIRIS_FOLLOW_UP_THOUGHT" in str(item):
                is_followup = True
                break
        
        # Also check the original message content directly
        if not is_followup:
            for msg in messages:
                content = msg.get('content', '') if isinstance(msg, dict) else str(msg)
                if "CIRIS_FOLLOW_UP_THOUGHT" in content:
                    is_followup = True
                    break
        
        if is_followup:
            # Follow-up thought → TASK_COMPLETE
            action = HandlerActionType.TASK_COMPLETE
            params = {}
            rationale = "Completing follow-up thought (detected CIRIS_FOLLOW_UP_THOUGHT)"
        else:
            # Default: new task → SPEAK
            action = HandlerActionType.SPEAK
            params = SpeakParams(content="Hello! How can I help you?")
            rationale = "Default speak action for new task"
""")