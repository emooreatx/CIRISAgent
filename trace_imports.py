#!/usr/bin/env python3
"""Trace what gets imported when loading IncomingMessage."""

import sys
import time
import importlib.util

# Track imports
imported_modules = []
import_times = {}

# Original __import__
original_import = __import__

def timed_import(name, *args, **kwargs):
    """Wrapper to time imports."""
    start = time.time()
    try:
        module = original_import(name, *args, **kwargs)
        end = time.time()
        duration = end - start
        
        if name not in import_times:
            import_times[name] = duration
            if duration > 0.01:  # Only log slow imports
                print(f"  Import {name}: {duration:.3f}s")
        
        return module
    except ImportError:
        raise

# Monkey patch import
__builtins__['__import__'] = timed_import

print("Tracing imports for ciris_engine.schemas.runtime.messages...\n")

start_total = time.time()
from ciris_engine.schemas.runtime.messages import IncomingMessage
end_total = time.time()

print(f"\nTotal import time: {end_total - start_total:.3f}s")

# Show slowest imports
print("\nSlowest imports:")
sorted_imports = sorted(import_times.items(), key=lambda x: x[1], reverse=True)
for module, duration in sorted_imports[:20]:
    if duration > 0.01:
        print(f"  {module}: {duration:.3f}s")

# Restore original import
__builtins__['__import__'] = original_import