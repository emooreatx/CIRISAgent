# Deployment Guide

This document outlines the steps to build the Docker image and run the CIRIS Agent Teacher container.

## Prerequisites

1.  **Docker Installed**: Ensure Docker is installed and running on your system.
2.  **Environment File**: An `env.sh` file must be present in the project root directory. This file should contain necessary environment variables for the agent. Example:
    ```bash
    export DISCORD_BOT_TOKEN="your_discord_bot_token"
    export OPENAI_API_KEY="your_openai_api_key"
    # Add other required environment variables
    ```
3.  **Docker Hub Account (Optional for local deployment, Required for pushing)**: If you intend to push the image to Docker Hub, you need an account and a `DOCKERHUB_TOKEN` environment variable set with a Personal Access Token.

## Building the Docker Image

The Docker image packages the CIRIS Agent Teacher application and its dependencies.

1.  **Navigate to the project root directory**:
    ```bash
    cd /path/to/your/CIRISAgent
    ```

2.  **Using the build script (`docker/deploy_teacher_discord.sh`)**:
    The `docker/deploy_teacher_discord.sh` script is designed to be run from the **project root directory**. It automates building the image, logging into Docker Hub (if `DOCKERHUB_TOKEN` is set), and pushing the image.
    ```bash
    ./docker/deploy_teacher_discord.sh
    ```
    This script will:
    *   Automatically navigate to the project root directory.
    *   Build the Docker image using `docker/Dockerfile` (the path is relative to the project root).
    *   Tag the image as `alignordie/cirisagent-teacher:latest` (or as configured in the script).
    *   If `DOCKERHUB_TOKEN` and `DOCKER_USERNAME` are correctly set as environment variables, it will attempt to log in to Docker Hub and push the image.

3.  **Manual build command**:
    Alternatively, you can build the image directly using the `docker build` command. Ensure you are in the **project root directory**:
    ```bash
    DOCKER_USERNAME="your_docker_username" # Or use "alignordie" as per scripts
    IMAGE_NAME="cirisagent-teacher"
    IMAGE_TAG="latest"
    FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"

    docker build -t "$FULL_IMAGE_NAME" -f docker/Dockerfile .
    ```

## Running the Docker Container

Once the image is built, you can run it as a Docker container.

1.  **Ensure `env.sh` is in the project root.** The container relies on this file for its environment configuration.

2.  **Using the run script**:
    The `docker/run_agent_teacher.sh` script is provided to simplify running the container. It also handles stopping and removing any pre-existing container with the same name to avoid conflicts.
    *   Make the script executable (if you haven't already):
        ```bash
        chmod +x docker/run_agent_teacher.sh
        ```
    *   Run the script from the `docker` directory or project root:
        ```bash
        ./docker/run_agent_teacher.sh
        ```
    This script will:
    *   Define the container name as `cirisagent-teacher-container`.
    *   Stop and remove any existing container with this name.
    *   Run the image `alignordie/cirisagent-teacher:latest` (or as configured) with the name `cirisagent-teacher-container`, mounting the `env.sh` file.

3.  **Manual run command**:
    If you prefer to run the container manually, use the following command from the project root. Make sure to replace placeholders if your configuration differs.
    ```bash
    DOCKER_USERNAME="alignordie"
    IMAGE_NAME="cirisagent-teacher"
    IMAGE_TAG="latest"
    FULL_IMAGE_NAME="$DOCKER_USERNAME/$IMAGE_NAME:$IMAGE_TAG"
    CONTAINER_NAME="cirisagent-teacher-container"

    # Optional: Stop and remove existing container if you want to reuse the name
    if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then docker stop "$CONTAINER_NAME"; fi
    if [ "$(docker ps -aq -f name=^/${CONTAINER_NAME}$)" ]; then docker rm "$CONTAINER_NAME"; fi

    docker run -it --name "$CONTAINER_NAME" --env-file env.sh "$FULL_IMAGE_NAME"
    ```
    *   `-it`: Runs the container in interactive mode with a pseudo-TTY.
    *   `--name "$CONTAINER_NAME"`: Assigns a specific name to the container.
    *   `--env-file env.sh`: Loads environment variables from the `env.sh` file located in the project root (relative to where `docker run` is executed, or use an absolute path).

## Stopping the Container

If you ran the container with a name (e.g., `cirisagent-teacher-container`), you can stop it using:
```bash
docker stop cirisagent-teacher-container
```

## Viewing Logs

To view the logs of a running or stopped container:
```bash
docker logs cirisagent-teacher-container
```
If the container is running in the foreground (`-it` without `-d`), logs will be streamed to your terminal.
