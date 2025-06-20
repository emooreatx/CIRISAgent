#!/usr/bin/env python3
"""
Simple test for SPEAK handler via SDK.
"""
import asyncio
from ciris_sdk import CIRISClient


async def test_speak():
    async with CIRISClient(base_url='http://localhost:8080') as client:
        # Test 1: Simple speak without special characters
        print("Test 1: Simple speak command")
        msg = await client.messages.send(
            content='$speak Hello from SDK test',
            channel_id='speak_simple'
        )
        print(f'Sent: {msg.id}')
        
        # Wait for response
        response = await client.messages.wait_for_response(
            channel_id='speak_simple',
            after_message_id=msg.id,
            timeout=10.0
        )
        
        if response:
            print(f'Got response: {response.content[:100]}...')
        else:
            print('No response received')
            
        # List all messages
        messages = await client.messages.list(channel_id='speak_simple')
        print(f'\nTotal messages: {len(messages)}')
        for m in messages:
            print(f'  [{m.author_name}]: {m.content[:50]}...')


if __name__ == "__main__":
    asyncio.run(test_speak())