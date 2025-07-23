#!/usr/bin/env python3
"""Simulate exact production bug."""

import os
os.environ['CIRIS_API_HOST'] = '0.0.0.0'
os.environ['CIRIS_API_PORT'] = '8080'

from ciris_engine.logic.adapters.api.config import APIAdapterConfig

print("=== SIMULATING PRODUCTION CODE ===")

# What main.py does
print("\n1. main.py creates config:")
main_config = APIAdapterConfig()
main_config.load_env_vars()
print(f"   Config after load_env_vars: host={main_config.host}")

# Simulating passing to adapter as kwargs['adapter_config']
kwargs = {'adapter_config': main_config}

print("\n2. APIAdapter.__init__ receives it:")
print(f"   adapter_config type: {type(kwargs['adapter_config'])}")
print(f"   adapter_config.host: {kwargs['adapter_config'].host}")

# What the OLD production code does (without my fix)
print("\n3. OLD adapter code execution:")
# Start with default configuration
config = APIAdapterConfig()
print(f"   Default config: host={config.host}")

# Load environment variables first
config.load_env_vars()
print(f"   After load_env_vars: host={config.host}")

# Then apply user-provided configuration (THIS IS THE BUG!)
if "adapter_config" in kwargs and kwargs["adapter_config"] is not None:
    if isinstance(kwargs["adapter_config"], APIAdapterConfig):
        print("   Replacing config with passed config...")
        config = kwargs["adapter_config"]  # This should preserve the env vars since main.py loaded them
        print(f"   After replacement: host={config.host}")

print(f"\n4. Final config used by uvicorn: host={config.host}")
print("\nSo the bug is NOT in this flow... Something else must be wrong!")