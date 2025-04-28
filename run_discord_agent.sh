#!/bin/bash

# CIRIS Discord Agent launcher
# This script runs the CIRIS Discord Agent from the project root

set -e  # Exit on error

# Ensure we're in the project root directory
cd "$(dirname "$0")"

# Set up Python path to find our modules
export PYTHONPATH="$PYTHONPATH:$(pwd)"

echo "Starting CIRIS Discord Agent..."
python src/agents/discord_agent/main.py "$@"
