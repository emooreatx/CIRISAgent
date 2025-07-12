#!/usr/bin/env python3
"""Debug Pydantic import slowness."""

import time

print("Testing Pydantic import timing...")

# Time basic imports
start = time.time()
import pydantic
end = time.time()
print(f"Import pydantic: {end - start:.3f}s")

start = time.time()
from pydantic import BaseModel, Field, ConfigDict
end = time.time()
print(f"Import BaseModel, Field, ConfigDict: {end - start:.3f}s")

# Now test our schema import
start = time.time()
from ciris_engine.schemas.runtime.messages import IncomingMessage
end = time.time()
print(f"Import IncomingMessage: {end - start:.3f}s")

# Check if it's a first-import issue
print("\nTesting repeated imports...")
start = time.time()
from ciris_engine.schemas.runtime.messages import DiscordMessage
end = time.time()
print(f"Import DiscordMessage (second import): {end - start:.3f}s")

# Check Pydantic version
print(f"\nPydantic version: {pydantic.__version__}")

# Check if there are any import side effects
import sys
print(f"\nNumber of loaded modules: {len(sys.modules)}")

# List modules that might be causing slowness
slow_modules = [name for name in sys.modules if 'pydantic' in name or 'ciris' in name]
print(f"Pydantic/CIRIS modules loaded: {len(slow_modules)}")