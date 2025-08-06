# Docker Configuration

This directory contains Docker configurations for running CIRIS in various modes.

## Mac Users - Important Notes

If you're on macOS (especially Apple Silicon/M1/M2), you may encounter build issues with `psutil` requiring `gcc`. We've included build tools in the Dockerfile to address this:

### Quick Fix for Mac Users:
```bash
# Use the provided build script which handles platform detection
cd docker
./build.sh

# Or build manually with platform flag for Apple Silicon
docker build --platform linux/amd64 -f docker/Dockerfile -t ciris:latest ..
```

### If you still have issues:
1. Update Docker Desktop to the latest version
2. Enable "Use Rosetta for x86/amd64 emulation" in Docker Desktop settings
3. Allocate at least 4GB RAM to Docker Desktop
4. Try the optimized multi-stage build: `docker build -f docker/Dockerfile.optimized -t ciris:optimized ..`

## Available Configurations

- `docker-compose.yml` - Default API server
- `docker-compose-mock.yml` - API server with mock LLM (for offline testing)
- `docker-compose-dev.yml` - Development setup with API + GUI hot reload
- `docker-compose-prod.yml` - Production setup with API + GUI
- `docker-compose-4-agents.yml` - Run all 4 agent profiles simultaneously

## Environment Files

All configurations support custom environment files. You can specify which env file to use via environment variables:

### Single Container Usage
```bash
# Use default .env
cd docker
docker compose up

# Use a specific env file
CIRIS_ENV_FILE=../ciris_student.env docker compose up

# Or set it in docker/.env
echo "CIRIS_ENV_FILE=../ciris_student.env" > .env
docker compose up
```

### Multiple Agents (4-agents configuration)
```bash
# Use default env files for each agent
cd docker
docker compose -f docker-compose-4-agents.yml up

# Or specify custom env files for each agent
CIRIS_ENV_FILE_SAGE=../my_sage.env \
CIRIS_ENV_FILE_SCOUT=../my_scout.env \
CIRIS_ENV_FILE_ECHO_CORE=../my_echo_core.env \
CIRIS_ENV_FILE_ECHO_SPEC=../my_echo_spec.env \
docker compose -f docker-compose-4-agents.yml up
```

## Quick Start

1. Copy the example env configuration:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` to point to your desired environment file:
   ```bash
   CIRIS_ENV_FILE=../ciris_student.env
   ```

3. Run your desired configuration:
   ```bash
   docker compose -f docker-compose-dev.yml up
   ```

## Port Mappings

- Default/Mock/Dev/Prod API: `8080`
- Dev/Prod GUI: `3000`
- 4-agents configuration:
  - sage: `8001`
  - scout: `8002`
  - echo-core: `8003`
  - echo-speculative: `8004`
