# Dual LLM Test Fixes

## Issue Summary
Two test failures related to dual LLM service configuration:
1. `test_second_llm_config_from_env` - IndexError: tuple index out of range
2. `test_dual_llm_service` (likely related to the same issue)

## Root Cause
The test was incorrectly trying to access mock call arguments as positional arguments when the actual implementation uses keyword arguments:

```python
# Test was trying to access:
second_config = second_call[0][0]  # First positional argument

# But OpenAICompatibleClient is called with keyword arguments:
openai_service = OpenAICompatibleClient(
    config=llm_config,
    telemetry_service=self.telemetry_service,
    time_service=self.time_service
)
```

## Fixes Applied

### 1. Fixed argument access in test_second_llm_config_from_env
Changed from:
```python
second_config = second_call[0][0]  # First positional argument
```

To:
```python
second_config = second_call.kwargs['config']  # Access keyword argument
```

### 2. Added missing mock method
Added `register_service` to the mock service registry fixture:
```python
registry.register_service = Mock()
```

## Results
All 4 dual LLM tests in `test_dual_llm_service.py` now pass:
- test_single_llm_service_without_second_key ✓
- test_dual_llm_service_with_second_key ✓
- test_second_llm_config_from_env ✓
- test_both_services_started ✓

## Note on Integration Test
The integration test `test_dual_llm_service_real_initialization` failure is unrelated to the tuple index error. It fails because GraphAuditService is missing dependencies in the test environment. This is a separate issue that would require a more complete test setup.

## Key Takeaway
When mocking function calls, always verify whether the function uses positional or keyword arguments. The OpenAICompatibleClient constructor exclusively uses keyword arguments, so tests must access mock call arguments accordingly.