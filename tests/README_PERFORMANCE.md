# Test Performance Improvements

This document describes the performance improvements made to the CIRIS test suite.

## Changes Made

### 1. Configurable API Timeout
- Added `interaction_timeout` configuration to `APIAdapterConfig`
- Default remains 30 seconds for production
- Can be overridden via `CIRIS_API_INTERACTION_TIMEOUT` environment variable
- Test configuration sets this to 5 seconds

### 2. Test-Specific Configuration
- Created `tests/test_config.env` with test-specific settings
- Automatically loaded by `conftest.py` when running tests
- Sets `CIRIS_API_INTERACTION_TIMEOUT=5.0` for faster test execution

### 3. Reduced Sleep Times
- Removed redundant `time.sleep()` calls after `wait_for_processing()`
- Reduced `wait_for_processing()` timeouts from 5s to 1-2s
- Capped maximum wait time at 1 second for tests
- Reduced SDK timeout from 35s to 10s

### 4. Test Organization
- Marked API tests with `pytest.mark.integration`
- Added global pytest timeout of 60 seconds per test
- Can exclude slow tests with: `pytest -m "not integration"`

### 5. Fast Test Runner
- Created `run_tests_fast.sh` script for optimized test runs
- Automatically sources test configuration
- Includes fail-fast options for quicker feedback

## Running Tests

### Run all tests with optimizations:
```bash
./run_tests_fast.sh
```

### Run only unit tests (exclude integration):
```bash
pytest -m "not integration"
```

### Run with custom timeout:
```bash
CIRIS_API_INTERACTION_TIMEOUT=2.0 pytest tests/
```

## Results

These changes should reduce test execution time by approximately:
- API interaction tests: 80-90% reduction (30s → 5s max per interaction)
- Handler tests: 60-70% reduction (removed redundant waits)
- Overall suite: 50-70% reduction depending on test mix

## Future Improvements

1. Implement proper polling instead of fixed sleeps
2. Add async test fixtures for parallel execution
3. Create mock responses that complete immediately
4. Add test categories for granular execution control