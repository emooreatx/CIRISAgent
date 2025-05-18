#!/bin/bash

# Configuration
DOCKER_USERNAME="alignordie"
IMAGE_NAME="cirisagent-teacher"
IMAGE_TAG="latest"
CONTAINER_NAME="cirisagent-teacher" # Added a specific container name

# Derived full image name
FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"

# Navigate to the project root to ensure env.sh is found
cd "$(dirname "$0")/.." || exit

# Check if the container is already running
if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "Stopping existing container: $CONTAINER_NAME"
    docker stop "$CONTAINER_NAME"
fi

# Check if the container exists (even if stopped)
if [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "Removing existing container: $CONTAINER_NAME"
    docker rm "$CONTAINER_NAME"
fi

echo "Running Docker image: $FULL_IMAGE_NAME as container: $CONTAINER_NAME"
docker run -it --name "$CONTAINER_NAME" --env-file ../env.sh "$FULL_IMAGE_NAME" # Added --name
