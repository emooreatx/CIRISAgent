"""CIRIS Engine - Core Agent Runtime and Services"""

__version__ = "0.1.0"

# Import key runtime components for easy access
from .runtime import get_ciris_runtime

__all__ = [
    "__version__",
    "get_ciris_runtime",
]
