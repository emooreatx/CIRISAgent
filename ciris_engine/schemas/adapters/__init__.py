"""
Adapter-specific schemas.

These schemas are used for adapter registration and management.
"""

from .registration import AdapterServiceRegistration
from .core import *  # Re-export API schemas if they exist

__all__ = [
    "AdapterServiceRegistration",
]
