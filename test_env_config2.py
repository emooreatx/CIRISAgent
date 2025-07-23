#!/usr/bin/env python3
"""Test env var loading with dict conversion."""

import os
os.environ['CIRIS_API_HOST'] = '0.0.0.0'
os.environ['CIRIS_API_PORT'] = '8080'

from ciris_engine.logic.adapters.api.config import APIAdapterConfig

print("Test: Dict conversion issue")
# What main.py does
config = APIAdapterConfig()
config.load_env_vars()
print(f"Original config: host={config.host}")

# Convert to dict and back (simulating serialization)
config_dict = config.model_dump()
print(f"Config as dict: {config_dict}")

# What happens if adapter receives dict
new_config = APIAdapterConfig(**config_dict)
print(f"Config from dict: host={new_config.host}")

# The bug case - creating new config from dict without loading env vars
buggy_config = APIAdapterConfig(**config_dict)
print(f"Buggy config (no env load): host={buggy_config.host}")