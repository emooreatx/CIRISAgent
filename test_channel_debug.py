#!/usr/bin/env python3
"""Debug test to find where 'test' channel is coming from."""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, '/home/emoore/CIRISAgent')

# Check where the test channel might be coming from
print("\n=== Searching for 'test' channel references ===\n")

# Check environment variables
print("Environment variables:")
for key, value in os.environ.items():
    if 'channel' in key.lower() or 'test' in value.lower():
        print(f"  {key}={value}")

# Check if there's a hardcoded test channel in the wakeup processor
import ciris_engine.persistence as persistence
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus

persistence.initialize_database()

# Get the most recent failed thoughts
thoughts = persistence.get_thoughts_by_status(ThoughtStatus.FAILED)
print(f"\nTotal failed thoughts: {len(thoughts)}")

# Find thoughts that mention 'test' in their final action
test_thoughts = []
for thought in thoughts[-100:]:  # Last 100 failed thoughts
    if hasattr(thought, 'final_action') and thought.final_action:
        if isinstance(thought.final_action, dict):
            error_str = str(thought.final_action.get('error', ''))
            if 'channel test' in error_str or 'channel_id=test' in error_str:
                test_thoughts.append((thought, error_str))

print(f"\nFailed thoughts mentioning 'test' channel: {len(test_thoughts)}")
for thought, error in test_thoughts[:5]:  # Show first 5
    print(f"\nThought {thought.thought_id}:")
    print(f"  Task: {thought.source_task_id}")
    print(f"  Created: {thought.created_at}")
    print(f"  Error: {error[:200]}...")
    
    # Check the task
    task = persistence.get_task_by_id(thought.source_task_id)
    if task:
        print(f"  Task description: {task.description}")
        if hasattr(task, 'context') and task.context:
            channel_context = getattr(task.context.system_snapshot, 'channel_context', None) if hasattr(task.context, 'system_snapshot') and task.context.system_snapshot else None
            if channel_context:
                channel_id = channel_context.channel_id if hasattr(channel_context, 'channel_id') else str(channel_context)
                print(f"  Task channel_id: {channel_id}")

# Check for test in the actual thought content
print("\n\nChecking thought content for 'test':")
test_content_thoughts = []
for thought in thoughts[-100:]:
    if hasattr(thought, 'content') and thought.content:
        content_str = str(thought.content)
        if 'channel.*test' in content_str or 'test.*channel' in content_str:
            test_content_thoughts.append(thought)

print(f"Thoughts with 'test' in content: {len(test_content_thoughts)}")

# Let's also check if there's something in the dispatched context
print("\n\nChecking most recent thoughts for channel info:")
all_thoughts = persistence.get_all_thoughts()
recent = sorted(all_thoughts, key=lambda t: t.created_at, reverse=True)[:20]

for thought in recent:
    if hasattr(thought, 'dispatched_action') and thought.dispatched_action:
        action = thought.dispatched_action
        if isinstance(action, dict) and 'channel' in str(action):
            print(f"\nThought {thought.thought_id}:")
            print(f"  Status: {thought.status.value}")
            print(f"  Action: {action}")