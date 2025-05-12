#!/bin/bash

# CIRIS Discord Student Agent launcher
# This script runs the CIRIS Discord Student Agent from the project root

set -e  # Exit on error

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Set up Python path to find our modules
# Adding src directory to make ciris_engine importable
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

echo "Starting CIRIS Discord Student Agent..."
# Use Python module syntax instead of direct script execution to handle relative imports
# Explicitly use python3.12 as packages are installed there
python3.12 -m src.agents.discord_agent.ciris_discord_bot_student "$@"
