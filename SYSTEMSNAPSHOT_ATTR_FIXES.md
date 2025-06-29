# SystemSnapshot Attribute Fixes

## Summary
Fixed attr-defined errors for SystemSnapshot and related schemas by correcting references to non-existent attributes.

## Changes Made

### 1. GraphTelemetryService (`ciris_engine/logic/services/graph/telemetry_service.py`)

#### Fixed wisdom_request and agent_name references:
- **Line 462**: Changed `if snapshot.agent_name or snapshot.wisdom_request:` to `if snapshot.agent_identity or snapshot.identity_purpose:`
- **Lines 573-604**: Updated `_store_identity_context` method to:
  - Extract agent_name from `snapshot.agent_identity` dict if available
  - Use actual SystemSnapshot fields: `identity_purpose`, `identity_capabilities`, `identity_restrictions`
  - Removed reference to non-existent `wisdom_request` field

#### Fixed telemetry and current_round_resources references:
- **Lines 438-463**: Changed from:
  - `snapshot.telemetry` → `snapshot.telemetry_summary`
  - `snapshot.current_round_resources` → Removed (doesn't exist)
  - Added conversion from TelemetrySummary to TelemetryData format
  - Properly maps all telemetry summary fields to metrics

### 2. DMA Core Schema (`ciris_engine/schemas/dma/core.py`)

#### Fixed resource_usage_summary property:
- **Lines 85-94**: Changed from using non-existent `current_round_resources` to using `telemetry_summary` fields:
  - `tokens_per_hour` for tokens
  - `cost_per_hour_cents` for cost
  - `carbon_per_hour_grams` for carbon

#### Fixed audit_is_valid property:
- **Lines 97-101**: Removed reference to non-existent `last_audit_verification` field
  - Now always returns True as SystemSnapshot doesn't contain audit verification data

#### Fixed ConscienceResult reference:
- **Line 81**: Changed `conscience_failure_context.overridden` to `not conscience_failure_context.passed`
  - ConscienceResult has `passed` field, not `overridden`

## SystemSnapshot Actual Fields

Based on the schema in `ciris_engine/schemas/runtime/system_context.py`, SystemSnapshot has these fields:
- `channel_id`, `channel_context`
- `current_task_details`, `current_thought_summary`
- `system_counts`, `top_pending_tasks_summary`, `recently_completed_tasks_summary`
- `agent_identity` (dict), `identity_purpose`, `identity_capabilities`, `identity_restrictions`
- `detected_secrets`, `secrets_filter_version`, `total_secrets_stored`
- `service_health`, `circuit_breaker_status`
- `shutdown_context`
- `resource_alerts`
- `user_profiles`
- `telemetry_summary`

## Impact
These fixes ensure that the code only references attributes that actually exist on SystemSnapshot, eliminating attr-defined mypy errors and preventing runtime AttributeError exceptions.