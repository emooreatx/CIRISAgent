__all__ = [
    "RuntimeInterface",
    "CIRISRuntime",
]

def get_runtime_interface() -> type:
    from .runtime_interface import RuntimeInterface
    return RuntimeInterface

def get_ciris_runtime() -> type:
    from .ciris_runtime import CIRISRuntime
    return CIRISRuntime
