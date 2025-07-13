# Test Failure Analysis - Post-Migration

## Summary
- **Total Tests**: 922
- **Passed**: 609 (66%)
- **Failed**: 36 (4%)
- **Errors**: 17 (2%)
- **Skipped**: 80 (9%)

## Failure Categories

### 1. Missing Attributes (24 failures)
- `AdaptiveFilterService` missing `llm` attribute (6 failures)
- `VisibilityService` missing `_running` attribute (2 failures)
- `InitializationService` missing `_running` attribute (2 failures)
- `ShutdownService` missing `_running` attribute (2 failures)
- `RuntimeControlService` missing `config_manager` attribute (12 failures)

### 2. Assertion Failures (12 failures)
- Service name mismatches (6 failures)
- Service type mismatches (4 failures)
- Version mismatches (2 failures)

### 3. Dependency Issues (11 failures)
- `GraphAuditService` missing required dependencies (11 failures)

### 4. Abstract Method Issues (3 failures)
- `PatternAnalysisLoop` missing abstract method implementations

## Root Causes

### 1. Lifecycle Attributes
Services previously tracked `_running` state manually, but BaseService doesn't expose this. Tests need updating to use `_started` or the service's health check.

### 2. Service Names
BaseService uses class name by default. Tests expect old hardcoded names.

### 3. Missing Dependencies
GraphAuditService now properly checks dependencies in BaseGraphService but tests aren't providing them.

### 4. Attribute Access
Some services had public attributes that are now private or removed during cleanup.

## Fixes Needed

### High Priority
1. Fix AdaptiveFilterService - restore `llm` attribute or update tests
2. Fix RuntimeControlService - expose `config_manager` or update tests
3. Fix GraphAuditService tests - provide required dependencies

### Medium Priority
4. Update lifecycle tests to use BaseService patterns
5. Fix service name/type assertions in tests
6. Implement missing abstract methods in PatternAnalysisLoop

### Low Priority
7. Update version assertions
8. Clean up deprecated test patterns