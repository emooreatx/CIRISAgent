#!/usr/bin/env python3
"""Test script to verify API observation creation."""

import requests
import json
import time

# Login to get token
login_response = requests.post(
    "http://localhost:8080/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
token = login_response.json()["access_token"]
print(f"Got token: {token[:20]}...")

# Send a message
message = "Hello API, can you hear me?"
interact_response = requests.post(
    "http://localhost:8080/v1/agent/interact",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": message}
)
result = interact_response.json()
message_id = result["data"]["message_id"]
print(f"\nSent message: {message}")
print(f"Message ID: {message_id}")
print(f"Initial response: {result['data']['response']}")

# Wait a bit for processing
print("\nWaiting 5 seconds for processing...")
time.sleep(5)

# Check conversation history
history_response = requests.get(
    "http://localhost:8080/v1/agent/history",
    headers={"Authorization": f"Bearer {token}"},
    params={"limit": 10}
)
history = history_response.json()

print("\nConversation history:")
for msg in history["data"]["messages"]:
    author = "Agent" if msg["is_agent"] else "User"
    print(f"  [{author}] {msg['content'][:100]}")

# Check agent status
status_response = requests.get(
    "http://localhost:8080/v1/agent/status",
    headers={"Authorization": f"Bearer {token}"}
)
status = status_response.json()["data"]
print(f"\nAgent status:")
print(f"  State: {status['cognitive_state']}")
print(f"  Messages processed: {status['messages_processed']}")
print(f"  Current task: {status['current_task']}")