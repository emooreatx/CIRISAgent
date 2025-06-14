# Simple import to avoid circular dependencies
__all__ = [
    "RuntimeInterface",
    "CIRISRuntime",
]

# Lazy imports to avoid circular dependencies
def get_runtime_interface():
    from .runtime_interface import RuntimeInterface
    return RuntimeInterface

def get_ciris_runtime():
    from .ciris_runtime import CIRISRuntime
    return CIRISRuntime
