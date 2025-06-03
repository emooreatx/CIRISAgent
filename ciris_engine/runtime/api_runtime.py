"""Backward compatibility shim for the old ``APIRuntime`` entrypoint.

Historically the API runtime was provided as ``ciris_engine.runtime.api_runtime``
under the class ``APIRuntime``. The implementation now lives in
``ciris_engine.runtime.api.api_runtime_entrypoint.APIRuntimeEntrypoint``. This
module re-exports that class under the old name so that existing imports
continue to function while emitting a deprecation warning."""

from __future__ import annotations

import warnings

from .api.api_runtime_entrypoint import APIRuntimeEntrypoint

warnings.warn(
    "APIRuntime has moved to ciris_engine.runtime.api.api_runtime_entrypoint."
    " Importing from ciris_engine.runtime.api_runtime is deprecated and will be"
    " removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

APIRuntime = APIRuntimeEntrypoint

__all__ = ["APIRuntime"]
