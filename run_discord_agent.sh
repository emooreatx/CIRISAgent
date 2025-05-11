#!/bin/bash

# CIRIS Discord Agent launcher
# This script runs the CIRIS Discord Agent from the project root

set -e  # Exit on error

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Set up Python path to find our modules
# Adding src directory to make ciris_engine importable
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

echo "Starting CIRIS Discord Agent..."
# Use Python module syntax instead of direct script execution to handle relative imports
python -m src.agents.discord_agent.ciris_discord_bot_alpha "$@"
