__all__ = [
    "RuntimeInterface",
    "CIRISRuntime",
]

def get_runtime_interface():
    from .runtime_interface import RuntimeInterface
    return RuntimeInterface

def get_ciris_runtime():
    from .ciris_runtime import CIRISRuntime
    return CIRISRuntime
