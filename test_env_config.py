#!/usr/bin/env python3
"""Test env var loading in API config."""

import os
os.environ['CIRIS_API_HOST'] = '0.0.0.0'
os.environ['CIRIS_API_PORT'] = '8080'

from ciris_engine.logic.adapters.api.config import APIAdapterConfig

print("Test 1: Default config with load_env_vars")
config1 = APIAdapterConfig()
print(f"Before load_env_vars: host={config1.host}")
config1.load_env_vars()
print(f"After load_env_vars: host={config1.host}")

print("\nTest 2: Config created from dict")
config2 = APIAdapterConfig(host="127.0.0.1", port=8080)
print(f"Before load_env_vars: host={config2.host}")
config2.load_env_vars()
print(f"After load_env_vars: host={config2.host}")

print("\nTest 3: What main.py does")
config3 = APIAdapterConfig()
config3.load_env_vars()
print(f"Config3 after load_env_vars: host={config3.host}")

# Simulate passing to adapter
print("\nTest 4: Simulating old adapter code")
# Start with default
config4 = APIAdapterConfig()
config4.load_env_vars()
print(f"Initial config with env: host={config4.host}")
# Then replace with passed config (this is the bug!)
config4 = config3  # This is what line 48 does: self.config = kwargs["adapter_config"]
print(f"After assignment: host={config4.host}")