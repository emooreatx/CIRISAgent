#!/usr/bin/env python3
"""Test the telemetry logs endpoint to verify it shows recent logs correctly."""

import asyncio
import requests
import json
from datetime import datetime, timezone

async def test_telemetry_logs():
    """Test the telemetry logs endpoint."""
    
    # First, let's authenticate
    auth_url = "http://localhost:8080/v1/auth/login"
    auth_data = {
        "username": "admin",
        "password": "ciris_admin_password"
    }
    
    print("1. Authenticating...")
    auth_response = requests.post(auth_url, json=auth_data)
    if auth_response.status_code != 200:
        print(f"   ❌ Authentication failed: {auth_response.status_code}")
        print(f"   Response: {auth_response.text}")
        return
    
    token = auth_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   ✅ Authentication successful")
    
    # Test the logs endpoint
    print("\n2. Fetching logs from telemetry endpoint...")
    logs_url = "http://localhost:8080/v1/telemetry/logs"
    
    # Get logs with a small limit to see recent entries
    params = {"limit": 20}
    logs_response = requests.get(logs_url, headers=headers, params=params)
    
    if logs_response.status_code != 200:
        print(f"   ❌ Failed to fetch logs: {logs_response.status_code}")
        print(f"   Response: {logs_response.text}")
        return
    
    logs_data = logs_response.json()
    logs = logs_data.get("data", {}).get("logs", [])
    
    print(f"   ✅ Fetched {len(logs)} log entries")
    
    # Display the logs
    print("\n3. Log entries (should be oldest first, newest last):")
    print("   " + "-" * 80)
    
    for i, log in enumerate(logs):
        timestamp = log.get("timestamp", "No timestamp")
        level = log.get("level", "UNKNOWN")
        service = log.get("service", "unknown")
        message = log.get("message", "No message")
        
        # Truncate long messages
        if len(message) > 100:
            message = message[:97] + "..."
        
        print(f"   [{i+1:2d}] {timestamp} | {level:8s} | {service:20s} | {message}")
    
    print("   " + "-" * 80)
    
    # Check order
    if logs:
        first_timestamp = logs[0].get("timestamp", "")
        last_timestamp = logs[-1].get("timestamp", "")
        
        print(f"\n4. Order check:")
        print(f"   First entry: {first_timestamp}")
        print(f"   Last entry:  {last_timestamp}")
        
        # Parse timestamps to check order
        try:
            first_dt = datetime.fromisoformat(first_timestamp.replace('Z', '+00:00'))
            last_dt = datetime.fromisoformat(last_timestamp.replace('Z', '+00:00'))
            
            if first_dt < last_dt:
                print("   ✅ Logs are in correct order (oldest first, newest last)")
            else:
                print("   ❌ Logs are in reverse order!")
        except Exception as e:
            print(f"   ⚠️  Could not parse timestamps: {e}")
    
    # Generate a new log entry to test real-time updates
    print("\n5. Generating a test log entry...")
    interact_url = "http://localhost:8080/v1/agent/interact"
    test_message = {
        "message": "$speak Testing telemetry logs at " + datetime.now(timezone.utc).isoformat(),
        "channel_id": "api_telemetry_test"
    }
    
    interact_response = requests.post(interact_url, headers=headers, json=test_message)
    if interact_response.status_code == 200:
        print("   ✅ Test message sent")
    else:
        print(f"   ⚠️  Test message failed: {interact_response.status_code}")
    
    # Wait a moment for logs to be written
    await asyncio.sleep(2)
    
    # Fetch logs again
    print("\n6. Fetching logs again to see if new entry appears...")
    logs_response2 = requests.get(logs_url, headers=headers, params=params)
    
    if logs_response2.status_code == 200:
        logs_data2 = logs_response2.json()
        logs2 = logs_data2.get("data", {}).get("logs", [])
        
        print(f"   ✅ Fetched {len(logs2)} log entries")
        
        # Show last 5 entries
        print("\n   Last 5 entries:")
        for i, log in enumerate(logs2[-5:]):
            timestamp = log.get("timestamp", "No timestamp")
            message = log.get("message", "No message")
            if len(message) > 80:
                message = message[:77] + "..."
            print(f"   [{i+1}] {timestamp} | {message}")
        
        # Check if our test message appears
        found_test = False
        for log in logs2:
            if "Testing telemetry logs" in log.get("message", ""):
                found_test = True
                break
        
        if found_test:
            print("\n   ✅ Test log entry found in results!")
        else:
            print("\n   ⚠️  Test log entry not found (might need more time)")

if __name__ == "__main__":
    asyncio.run(test_telemetry_logs())