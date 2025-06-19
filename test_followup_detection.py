#!/usr/bin/env python3
"""Test follow-up detection in mock LLM"""

from ciris_engine.services.mock_llm.responses_action_selection import action_selection

# Test with follow_up thought type in system message
messages = [
    {"role": "system", "content": "THOUGHT_TYPE=follow_up\n\nCovenant text here..."},
    {"role": "system", "content": "Other system prompt"},
    {"role": "user", "content": "Some user content"}
]

context = []

result = action_selection(context)

print(f"Selected action: {result.selected_action}")
print(f"Rationale: {result.rationale}")

if hasattr(result, 'action_parameters'):
    print(f"Parameters: {result.action_parameters}")
    
# Test with observation thought type
messages2 = [
    {"role": "system", "content": "THOUGHT_TYPE=observation\n\nCovenant text here..."},
    {"role": "system", "content": "Other system prompt"},
    {"role": "user", "content": "Some user content"}
]

result2 = action_selection(context)

print(f"\nObservation thought:")
print(f"Selected action: {result2.selected_action}")
print(f"Rationale: {result2.rationale}")