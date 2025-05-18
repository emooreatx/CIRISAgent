#!/bin/bash

# Configuration
DOCKER_USERNAME="alignordie"
IMAGE_NAME="cirisagent-teacher" # You can change this to your preferred image name
IMAGE_TAG="latest"

# Derived full image name
FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"

# Navigate to the project root
cd "$(dirname "$0")/.." || exit

# Environment variables are assumed to be set externally

echo "Building Docker image: $FULL_IMAGE_NAME"
docker build -t "$FULL_IMAGE_NAME" -f docker/Dockerfile .

if [ $? -ne 0 ]; then
    echo "Docker build failed. Please check the output above."
    exit 1
fi

echo "Docker image built successfully: $FULL_IMAGE_NAME"

echo ""
echo "Attempting to log in to Docker Hub..."
echo -n "$DOCKERHUB_TOKEN" | docker login -u "$DOCKER_USERNAME" --password-stdin

if [ $? -ne 0 ]; then
    echo "Docker login failed. Please check your credentials and try again."
    exit 1
fi

echo "Logged in successfully."
echo ""
echo "Pushing image to Docker Hub: $FULL_IMAGE_NAME"
docker push "$FULL_IMAGE_NAME"

if [ $? -ne 0 ]; then
    echo "Docker push failed. Please check the output above."
    exit 1
fi

echo "Image pushed successfully to $FULL_IMAGE_NAME"
echo "You can run it with: docker run -it --env-file env.sh $FULL_IMAGE_NAME"
