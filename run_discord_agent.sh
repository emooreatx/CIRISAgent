#!/bin/bash

# CIRIS Discord Agent launcher
# This script runs the CIRIS Discord Agent from the project root

set -e  # Exit on error

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Set up Python path to find our modules
export PYTHONPATH="/home/emoore/.local/lib/python3.12/site-packages:$(pwd):$PYTHONPATH"

echo "Starting CIRIS Discord Agent..."
python src/agents/discord_agent/ciris_discord_bot_alpha.py "$@"
