"""CIRIS Engine - Core Agent Runtime and Services"""

__version__ = "0.1.0"

# Import key runtime components for easy access
from .runtime import CIRISRuntime, RuntimeInterface

__all__ = [
    "__version__",
    "CIRISRuntime",
    "RuntimeInterface",
]
