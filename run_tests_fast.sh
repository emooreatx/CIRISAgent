#!/bin/bash
# Script to run tests with optimized configuration for speed

# Source the test configuration
if [ -f tests/test_config.env ]; then
    source tests/test_config.env
fi

# Run tests with additional optimizations
echo "Running tests with optimized configuration..."
echo "API interaction timeout: ${CIRIS_API_INTERACTION_TIMEOUT:-5.0}s"

# Run pytest with optimizations
pytest tests/ \
    -v \
    --timeout=60 \
    --maxfail=3 \
    -x \
    "$@"