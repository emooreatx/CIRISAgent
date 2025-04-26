#!/bin/bash

# Define variables
ARANGO_PORT=8529
CONTAINER_NAME="ciris-arangodb"
DATA_DIR="$(pwd)/data/arangodb"
ROOT_USERNAME=${ARANGO_USERNAME:-"root"}
ROOT_PASSWORD=${ARANGO_PASSWORD:-"cirispassword"}

# Ensure the data directory exists
mkdir -p "$DATA_DIR"
echo "Created data directory: $DATA_DIR"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container $CONTAINER_NAME already exists"
    
    # Check if it's running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "Container is already running"
        echo "Access ArangoDB at: http://localhost:$ARANGO_PORT"
        exit 0
    else
        echo "Starting existing container..."
        docker start "$CONTAINER_NAME"
        echo "Container started successfully"
        echo "Access ArangoDB at: http://localhost:$ARANGO_PORT"
        exit 0
    fi
fi

# Run ArangoDB container
echo "Starting new ArangoDB container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "$ARANGO_PORT:8529" \
    -e ARANGO_ROOT_PASSWORD="$ROOT_PASSWORD" \
    -v "$DATA_DIR:/var/lib/arangodb3" \
    arangodb:latest

# Check if container started successfully
if [ $? -eq 0 ]; then
    echo "ArangoDB container started successfully"
    echo "Access ArangoDB at: http://localhost:$ARANGO_PORT"
    echo "Username: $ROOT_USERNAME"
    echo "Password: $ROOT_PASSWORD"
    echo ""
    echo "To stop the container: docker stop $CONTAINER_NAME"
    echo "To remove the container: docker rm $CONTAINER_NAME"
    echo ""
    echo "Note: Your data is persisted in $DATA_DIR"
else
    echo "Failed to start ArangoDB container"
    exit 1
fi