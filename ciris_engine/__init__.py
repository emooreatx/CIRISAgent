"""CIRIS Engine - Core Agent Runtime and Services"""

__version__ = "0.1.0"

# Import key runtime components for easy access
from .logic.runtime.ciris_runtime import CIRISRuntime
from .logic.runtime.runtime_interface import RuntimeInterface

__all__ = [
    "__version__",
    "CIRISRuntime",
    "RuntimeInterface",
]
