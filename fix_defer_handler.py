#!/usr/bin/env python3
"""
Fix for the defer handler in mock LLM.
The issue is that the mock LLM is not correctly parsing the $defer command
from the user messages.
"""

# The fix would be to ensure that when extracting user input from messages,
# we preserve the $ prefix for commands.

# In responses_action_selection.py, around line 384-410, the code extracts
# the actual user input from messages and checks if it starts with $.
# The extraction is working correctly (as we tested), but the issue might be
# that the context items don't include the proper user input.

# Let's create a test to verify the exact issue:

import sys
sys.path.append('/app' if '/app' in sys.path else '.')

from ciris_modular_services.mock_llm.responses import extract_context_from_messages

# Test with a defer message
messages = [
    {"role": "system", "content": "You are Scout"},
    {"role": "user", "content": "@ADMIN (ID: ADMIN): $defer I'll handle this complex task later"}
]

context = extract_context_from_messages(messages)
print("Extracted context:")
for item in context:
    print(f"  - {item}")

# Check if user input is extracted
user_input_found = False
for item in context:
    if item.startswith("user_input:") or item.startswith("task:") or item.startswith("content:"):
        print(f"\nFound user input item: {item}")
        user_input_found = True

if not user_input_found:
    print("\n❌ No user input found in context - this is the problem!")
    print("\nThe issue is that extract_context_from_messages doesn't extract user input")
    print("It only extracts echo patterns but not the actual task/user_input")