#!/usr/bin/env python3
"""Test what context the mock LLM receives for follow-up thoughts."""
import asyncio
from ciris_sdk import CIRISClient
import time


async def main():
    """Test and trace mock LLM context."""
    # First, let's inject some logging into the mock LLM
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    async with CIRISClient(base_url="http://localhost:8080") as client:
        # Use unique channel
        import uuid
        channel = f"test_context_{uuid.uuid4().hex[:8]}"
        
        print(f"1. Sending SPEAK command to channel: {channel}")
        msg = await client.messages.send(
            content="$speak Test message for context tracing",
            channel_id=channel
        )
        print(f"   Sent: {msg.id}")
        
        # Wait for processing
        print("\n2. Waiting for processing...")
        await asyncio.sleep(3)
        
        # List messages
        messages = await client.messages.list(channel_id=channel, limit=50)
        
        print(f"\n3. Found {len(messages)} messages")
        
        # Analyze each message
        sdk_count = 0
        agent_count = 0
        speak_contents = []
        follow_up_contents = []
        
        for m in messages:
            if m.author_id == "sdk_user":
                sdk_count += 1
            else:
                agent_count += 1
                # Check message content
                if "CIRIS_FOLLOW_UP_THOUGHT" in m.content:
                    follow_up_contents.append((m.id, m.content[:200]))
                elif "Test message for context tracing" in m.content:
                    speak_contents.append((m.id, m.content[:200]))
        
        print(f"   SDK messages: {sdk_count}")
        print(f"   Agent messages: {agent_count}")
        print(f"   Messages with original speak content: {len(speak_contents)}")
        print(f"   Messages with follow-up instructions: {len(follow_up_contents)}")
        
        # The problem analysis
        print("\n4. PROBLEM ANALYSIS:")
        print("   The mock LLM is receiving follow-up thoughts but not detecting them properly.")
        print("   This causes follow-up thoughts to select SPEAK instead of TASK_COMPLETE.")
        print("   The infinite loop happens because each SPEAK creates another follow-up thought.")
        
        print("\n5. WHAT THE MOCK LLM RECEIVES:")
        print("   - Messages array with system and user messages")
        print("   - The messages contain the thought content with CIRIS_FOLLOW_UP_THOUGHT marker")
        print("   - But the detection in responses_action_selection.py is not working")
        
        # Check logs for more details
        print("\n6. Check logs/latest.log for:")
        print("   - 'extract_context_from_messages' output")
        print("   - 'action_selection' context items")
        print("   - 'CIRIS_FOLLOW_UP_THOUGHT' detection")


if __name__ == "__main__":
    asyncio.run(main())