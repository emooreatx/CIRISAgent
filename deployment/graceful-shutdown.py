#!/usr/bin/env python3
"""
Graceful shutdown script for CIRIS agents.

This script sends a graceful shutdown message to a running CIRIS agent,
allowing it to complete current tasks before exiting with code 0.
When used with CIRIS Manager, the agent will automatically restart
with the latest image after shutdown.
"""
import os
import sys
import json
import requests
import argparse
from pathlib import Path


def get_auth_token(agent_url):
    """Get authentication token by logging in with admin credentials."""
    # Try to read from .ciris/auth.json if it exists
    auth_file = Path.home() / ".ciris" / "auth.json"
    if auth_file.exists():
        try:
            with open(auth_file) as f:
                auth_data = json.load(f)
                token = auth_data.get("token")
                if token:
                    return token
        except:
            pass
    
    # Login to get a proper JWT token
    login_data = {
        "username": "admin",
        "password": "ciris_admin_password"
    }
    
    try:
        response = requests.post(
            f"{agent_url}/v1/auth/login",
            json=login_data,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error during login: {e}")
        return None


def send_shutdown_message(agent_url, message, token):
    """Send graceful shutdown message to agent."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # First, send the shutdown message via interact endpoint
    interact_data = {
        "message": message,
        "channel_id": "cli_graceful_shutdown"
    }
    
    try:
        response = requests.post(
            f"{agent_url}/v1/agent/interact",
            headers=headers,
            json=interact_data,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✓ Shutdown message sent: {message}")
        else:
            print(f"⚠ Failed to send message: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False
    
    # Now trigger the actual shutdown via runtime control
    shutdown_data = {
        "reason": message
    }
    
    try:
        response = requests.post(
            f"{agent_url}/v1/system/runtime/shutdown",
            headers=headers,
            json=shutdown_data,
            timeout=10
        )
        
        if response.status_code in [200, 202]:
            print("✓ Graceful shutdown initiated")
            return True
        else:
            print(f"⚠ Failed to initiate shutdown: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error initiating shutdown: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Gracefully shutdown CIRIS agent")
    parser.add_argument(
        "--agent-url",
        default="http://localhost:8080",
        help="Agent API URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--message",
        default="New build available! Docker container staged, shutdown to apply immediately",
        help="Shutdown message to send"
    )
    parser.add_argument(
        "--token",
        help="Authentication token (default: uses admin credentials)"
    )
    
    args = parser.parse_args()
    
    # Get authentication token
    token = args.token or get_auth_token(args.agent_url)
    
    if not token:
        print("❌ Failed to obtain authentication token")
        sys.exit(1)
    
    print(f"🔄 Sending graceful shutdown to {args.agent_url}")
    print(f"📝 Message: {args.message}")
    
    # Check if agent is healthy first
    try:
        response = requests.get(f"{args.agent_url}/v1/system/health", timeout=5)
        if response.status_code != 200:
            print("⚠ Agent health check failed - it may not be running")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to agent: {e}")
        sys.exit(1)
    
    # Send shutdown message
    if send_shutdown_message(args.agent_url, args.message, token):
        print("\n✅ Graceful shutdown initiated successfully!")
        print("   The agent will complete current tasks and exit with code 0.")
        print("   The staged container will automatically start once shutdown completes.")
    else:
        print("\n❌ Failed to initiate graceful shutdown")
        sys.exit(1)


if __name__ == "__main__":
    main()