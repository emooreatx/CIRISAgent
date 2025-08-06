# Pytest Docker Environment

This Docker setup emulates the GitHub Actions CI environment as closely as possible to help reproduce and debug CI test failures locally.

## Features

- **Python 3.12.11**: Exact version used in GitHub Actions CI
- **Ubuntu-based environment**: Similar to `ubuntu-latest` runner
- **All dependencies**: Installs all requirements.txt dependencies
- **CI environment variable**: Sets `CI=true` to match GitHub Actions
- **Coverage reporting**: Generates `coverage.xml` just like CI
- **Clean state**: Removes cache and test databases before running

## Usage

### Build and run all tests:
```bash
cd docker
docker-compose -f docker-compose-pytest.yml up --build
```

### Run specific tests:
```bash
# Run only Discord adapter tests (the failing ones)
docker-compose -f docker-compose-pytest.yml run pytest pytest tests/adapters/test_discord/ -v

# Run with more verbose output
docker-compose -f docker-compose-pytest.yml run pytest pytest -vv

# Run specific test file
docker-compose -f docker-compose-pytest.yml run pytest pytest tests/adapters/test_discord/test_discord_adapter_unit.py -v
```

### Interactive debugging:
```bash
# Start container with bash shell
docker-compose -f docker-compose-pytest.yml run pytest /bin/bash

# Then inside container:
pytest tests/adapters/test_discord/test_discord_adapter_unit.py::TestDiscordAdapter::test_send_message_success -vv
```

### View coverage report:
```bash
# After tests run, coverage.xml will be in the container
docker-compose -f docker-compose-pytest.yml run pytest cat coverage.xml
```

## Reproducing the CI Failures

The CI shows 6 failing Discord adapter tests all related to:
```
sqlite3.OperationalError: no such table: service_correlations
```

To reproduce these specific failures:
```bash
docker-compose -f docker-compose-pytest.yml run pytest pytest tests/adapters/test_discord/ tests/ciris_engine/logic/adapters/discord/ -v
```

## Differences from Production Docker

This Dockerfile is specifically for testing and differs from the production Dockerfile:
- Includes pytest and coverage tools
- Sets CI environment variable
- Cleans test artifacts before running
- Default command runs pytest instead of main.py

## Troubleshooting

1. **If tests pass locally but fail in CI**: Check that you've rebuilt the Docker image with `--build` flag to ensure latest code changes are included.

2. **Database errors**: The `service_correlations` table error suggests a missing database migration. Check the migration files in the codebase.

3. **Permission errors**: If you get permission errors, ensure the mounted volumes have correct permissions.

4. **Different test results**: Make sure you're using the exact same Python version (3.12.11) and have CI=true set.
