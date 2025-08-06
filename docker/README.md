# CIRIS Docker Images

This directory contains all Dockerfiles for the CIRIS system, organized by component.

## Structure

```
docker/
├── agent/           # Core CIRIS agent
├── gui/             # Web GUI interface
├── voice/           # Voice components
└── compose/         # Docker Compose files
```

## Agent Images

### Production (`agent/Dockerfile`)
- Multi-stage build for minimal size
- Runs as non-root user (ciris:1000)
- Optimized for production deployment
- Health check included

### Development (`agent/Dockerfile.dev`)
- Includes debugging tools (ipdb, ipython, vim)
- Full build dependencies retained
- Environment variable `CIRIS_DEV_MODE=true`
- Suitable for local development

### Testing (`agent/Dockerfile.test`)
- Matches GitHub Actions CI environment
- Includes pytest and coverage tools
- Designed for running test suites

## GUI Image (`gui/Dockerfile`)
- Node.js 20 Alpine-based
- Next.js application
- Production build optimized

## Voice Components (`voice/Dockerfile`)
- Python 3.11 slim
- Includes ffmpeg for audio processing
- Runs as non-root user (wyoming)

## Building Images

### Production Build
```bash
docker build -f docker/agent/Dockerfile -t ciris-agent:latest .
```

### Development Build
```bash
docker build -f docker/agent/Dockerfile.dev -t ciris-agent:dev .
```

### GUI Build
```bash
docker build -f docker/gui/Dockerfile -t ciris-gui:latest CIRISGUI/
```

## Using Docker Compose

See `deployment/` directory for Docker Compose configurations:
- `docker-compose.dev.yml` - Development environment
- `docker-compose.production.yml` - Production multi-agent setup
