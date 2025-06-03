#!/usr/bin/env bash
set -e
# Set the root directory for the project
ROOT_DIR="$(dirname "$0")/../.."

# Kill any existing processes first
pkill -f "python.*main.py" || true
pkill -f "next.*dev" || true
pkill -f "pnpm.*dev" || true

# Source environment variables
if [ -f "$ROOT_DIR/.env" ]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
    echo "Sourced .env file"
fi

# Start CIRISAgent API with correct Python path
cd "$ROOT_DIR" && PYTHONPATH="$ROOT_DIR:$PYTHONPATH" python CIRISGUI/apps/ciris-api/main.py &
API_PID=$!

# Start Next.js
cd "$(dirname "$0")/../apps/agui" && pnpm dev --port 3000 &
WEB_PID=$!

trap "echo 'Stopping…'; kill $API_PID $WEB_PID" INT
wait
