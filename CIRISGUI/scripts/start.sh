#!/usr/bin/env bash
set -e
# Start CIRISAgent API
poetry run --directory "$(dirname "$0")/../apps/ciris-api" python main.py &
API_PID=$!
# Start Next.js
pnpm --filter agui dev --dir "$(dirname "$0")/.." --port 3000 &
WEB_PID=$!

trap "echo 'Stopping…'; kill $API_PID $WEB_PID" INT
wait
