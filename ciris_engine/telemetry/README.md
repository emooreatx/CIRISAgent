# Telemetry Module

This module provides minimal observability features for the CIRIS engine.

- `resource_monitor.py` implements lightweight resource monitoring with optional
  psutil integration.
- `metrics.py`, `security.py`, and `core.py` host the broader telemetry system.

Services should import `ResourceMonitor`, `TelemetryService`, and the
`SecurityFilter` via `ciris_engine.telemetry`.
