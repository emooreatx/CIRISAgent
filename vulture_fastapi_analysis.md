# Vulture False Positives Analysis: FastAPI Routes

## Summary

Analyzed all Python files in `ciris_engine/logic/adapters/api/routes/` for functions that vulture might report as unused but are actually used through decorators or other mechanisms.

## 1. FastAPI Route Functions (78 total)

These functions are registered via FastAPI decorators (@router.get, @router.post, etc.) and should be whitelisted in vulture:

### Agent Routes (`agent.py`)
- `interact` (line 120) - @router.post
- `get_history` (line 215) - @router.get
- `get_status` (line 385) - @router.get
- `get_identity` (line 512) - @router.get
- `get_channels` (line 636) - @router.get
- `websocket_stream` (line 786) - @router.websocket

### Audit Routes (`audit.py`)
- `query_audit_entries` (line 109) - @router.get
- `get_audit_entry` (line 180) - @router.get
- `search_audit_trails` (line 276) - @router.post
- `verify_audit_entry` (line 311) - @router.post
- `export_audit_data` (line 334) - @router.post

### Auth Routes (`auth.py`)
- `login` (line 44) - @router.post
- `logout` (line 112) - @router.post
- `get_current_user` (line 130) - @router.get
- `refresh_token` (line 163) - @router.post
- `list_oauth_providers` (line 221) - @router.get
- `configure_oauth_provider` (line 261) - @router.post
- `oauth_login` (line 317) - @router.get
- `oauth_callback` (line 409) - @router.post

### Config Routes (`config.py`)
- `list_configs` (line 44) - @router.get
- `get_config` (line 94) - @router.get
- `update_config` (line 138) - @router.put
- `delete_config` (line 202) - @router.delete

### Emergency Routes (`emergency.py`)
- `emergency_shutdown` (line 165) - @router.post
- `test_emergency_endpoint` (line 286) - @router.get

### Memory Routes (`memory.py`)
- `store_memory` (line 116) - @router.post
- `query_memory` (line 145) - @router.post
- `forget_memory` (line 266) - @router.delete
- `get_timeline` (line 314) - @router.get
- `recall_memory` (line 610) - @router.get
- `get_memory_stats` (line 625) - @router.get
- `get_memory` (line 706) - @router.get
- `visualize_memory_graph` (line 754) - @router.get
- `create_edge` (line 1748) - @router.post
- `get_node_edges` (line 1776) - @router.get

### System Routes (`system.py`)
- `get_system_health` (line 139) - @router.get
- `get_system_time` (line 226) - @router.get
- `get_resource_usage` (line 280) - @router.get
- `control_runtime` (line 323) - @router.post
- `get_services_status` (line 411) - @router.get
- `shutdown_system` (line 586) - @router.post
- `list_adapters` (line 659) - @router.get
- `get_adapter_status` (line 725) - @router.get
- `load_adapter` (line 785) - @router.post
- `unload_adapter` (line 838) - @router.delete
- `reload_adapter` (line 879) - @router.put
- `get_available_tools` (line 936) - @router.get

### System Extensions Routes (`system_extensions.py`)
- `get_processing_queue_status` (line 23) - @router.get
- `single_step_processor` (line 57) - @router.post
- `get_service_health_details` (line 103) - @router.get
- `update_service_priority` (line 129) - @router.put
- `reset_service_circuit_breakers` (line 167) - @router.post
- `get_service_selection_explanation` (line 195) - @router.get
- `get_processor_states` (line 231) - @router.get

### Telemetry Routes (`telemetry.py`)
- `get_telemetry_overview` (line 332) - @router.get
- `get_resource_telemetry` (line 358) - @router.get
- `get_detailed_metrics` (line 443) - @router.get
- `get_reasoning_traces` (line 560) - @router.get
- `get_system_logs` (line 707) - @router.get
- `query_telemetry` (line 812) - @router.post
- `get_detailed_metric` (line 1014) - @router.get
- `get_resource_history` (line 1111) - @router.get

### Telemetry Metrics Routes (`telemetry_metrics.py`)
- `get_metric_detail` (line 12) - @router.get

### User Routes (`users.py`)
- `list_users` (line 110) - @router.get
- `create_user` (line 168) - @router.post
- `get_user` (line 205) - @router.get
- `update_user` (line 248) - @router.put
- `change_password` (line 283) - @router.put
- `mint_wise_authority` (line 323) - @router.post
- `check_wa_key_exists` (line 438) - @router.get
- `deactivate_user` (line 496) - @router.delete
- `list_user_api_keys` (line 523) - @router.get
- `update_user_permissions` (line 555) - @router.put

### Wise Authority Routes (`wa.py`)
- `get_deferrals` (line 30) - @router.get
- `resolve_deferral` (line 102) - @router.post
- `get_permissions` (line 193) - @router.get
- `get_wa_status` (line 256) - @router.get
- `request_guidance` (line 329) - @router.post

## 2. Pydantic Serializer Functions (13 total)

These functions are used by Pydantic for field serialization and should be whitelisted:

- `serialize_timestamp` in telemetry.py (lines 34, 100, 117, 136)
- `serialize_times` in telemetry.py (line 155)
- `serialize_updated_at` in config.py (line 29)
- `validate_query_params` in memory.py (line 76) - @model_validator
- `serialize_times` in memory.py (line 98)
- `serialize_dates` in memory.py (line 111)
- `serialize_ts` in system.py (lines 43, 107, 126)
- `serialize_times` in system.py (line 55)
- `serialize_timestamp` in audit.py (line 36)

## 3. Helper Functions (21 total)

These are internal helper functions that are used within their modules:

### Used Internally
- `store_message_response` in agent.py (line 110)
- `notify_interact_response` in agent.py (line 776)
- `_convert_audit_entry` in audit.py (line 63)
- `_get_audit_service` in audit.py (line 100)
- `verify_signature` in emergency.py (line 44)
- `verify_timestamp` in emergency.py (line 116)
- `is_authorized_key` in emergency.py (line 146)
- `_get_edge_color` in memory.py (line 1273)
- `_get_edge_style` in memory.py (line 1298)
- `_get_node_color` in memory.py (line 1324)
- `_get_node_size` in memory.py (line 1340)
- `_hierarchy_pos` in memory.py (line 1360)
- `_calculate_timeline_layout` in memory.py (line 1400)
- `_generate_svg` in memory.py (line 1558)
- `_get_system_overview` in telemetry.py (line 167)
- `get_node_time` in memory.py (line 495)
- `get_node_sort_time` in memory.py (line 1008)
- `_hierarchy_pos_recursive` in memory.py (line 1367)
- `calculate_stats` in telemetry.py (line 1155)

### LogFileReader Class Methods (telemetry_logs_reader.py)
- `__init__` (line 40)
- `_get_actual_log_files` (line 43)
- `read_logs` (line 97)
- `_parse_log_file` (line 126)
- `_tail` (line 168)
- `_parse_log_line` (line 206)

## 4. Actually Unused Functions

After thorough analysis, NO functions were found to be actually unused. All functions are either:
1. Registered as FastAPI routes
2. Used as Pydantic serializers/validators
3. Helper functions used internally
4. Class methods

## Vulture Whitelist

To whitelist these in vulture, add the following to your `.vulture_whitelist.py` or vulture configuration:

```python
# FastAPI route handler functions - registered via decorators
_.interact  # ciris_engine/logic/adapters/api/routes/agent.py
_.get_history  # ciris_engine/logic/adapters/api/routes/agent.py
_.get_status  # ciris_engine/logic/adapters/api/routes/agent.py
_.get_identity  # ciris_engine/logic/adapters/api/routes/agent.py
_.get_channels  # ciris_engine/logic/adapters/api/routes/agent.py
_.websocket_stream  # ciris_engine/logic/adapters/api/routes/agent.py
# ... (continue for all 78 route functions)

# Pydantic field serializers
_.serialize_timestamp  # ciris_engine/logic/adapters/api/routes/telemetry.py
_.serialize_times  # ciris_engine/logic/adapters/api/routes/telemetry.py
_.serialize_updated_at  # ciris_engine/logic/adapters/api/routes/config.py
# ... (continue for all serializers)

# Helper functions used internally
_.store_message_response  # ciris_engine/logic/adapters/api/routes/agent.py
_.notify_interact_response  # ciris_engine/logic/adapters/api/routes/agent.py
# ... (continue for helper functions if needed)
```