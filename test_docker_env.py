#!/usr/bin/env python3
"""Test Docker environment file"""

import os

# Test loading the docker env file
env_vars = {}
with open('.env.docker', 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            env_vars[key] = value

print("=== Docker Environment Variables ===")
print(f"Total variables: {len(env_vars)}")
print("\nDiscord-related variables:")
for key, value in env_vars.items():
    if 'DISCORD' in key:
        if 'TOKEN' in key:
            print(f"{key}: {value[:20]}...{value[-10:] if len(value) > 30 else value}")
        else:
            print(f"{key}: {value}")

print("\nLLM-related variables:")
for key, value in env_vars.items():
    if 'OPENAI' in key or 'LLM' in key:
        if 'KEY' in key:
            print(f"{key}: {value[:20]}...{value[-10:] if len(value) > 30 else value}")
        else:
            print(f"{key}: {value}")

# Check for template-related variables
print("\nTemplate/Identity variables:")
for key, value in env_vars.items():
    if 'TEMPLATE' in key or 'IDENTITY' in key or 'AGENT' in key:
        print(f"{key}: {value}")

# Check if all required Discord vars are present
required_discord = ['DISCORD_BOT_TOKEN', 'DISCORD_HOME_CHANNEL_ID', 'DISCORD_CHANNEL_IDS']
print("\n=== Required Discord Variables Check ===")
for var in required_discord:
    if var in env_vars:
        print(f"✅ {var}: Present")
    else:
        print(f"❌ {var}: MISSING")