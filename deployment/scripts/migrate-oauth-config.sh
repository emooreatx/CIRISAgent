#!/bin/bash
# Script to migrate OAuth configuration to shared volume

set -e

echo "Migrating OAuth configuration to shared volume..."

# Create shared directory
mkdir -p /home/ciris/shared/oauth

# Copy from running container if it exists
if docker ps | grep -q ciris-agent-datum; then
    echo "Copying OAuth config from running container..."
    docker cp ciris-agent-datum:/home/ciris/.ciris/oauth.json /home/ciris/shared/oauth/oauth.json 2>/dev/null || echo "No OAuth config in container"
fi

# Copy from host if it exists and container didn't have it
if [ ! -f "/home/ciris/shared/oauth/oauth.json" ] && [ -f "/home/ciris/.ciris/oauth.json" ]; then
    echo "Copying OAuth config from host..."
    cp /home/ciris/.ciris/oauth.json /home/ciris/shared/oauth/
fi

# Set permissions
if [ -f "/home/ciris/shared/oauth/oauth.json" ]; then
    chmod 600 /home/ciris/shared/oauth/oauth.json
    echo "OAuth configuration migrated successfully"
    echo "Content:"
    cat /home/ciris/shared/oauth/oauth.json | jq . 2>/dev/null || cat /home/ciris/shared/oauth/oauth.json
else
    echo "No OAuth configuration found to migrate"
fi