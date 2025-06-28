"""
Adapter-specific schemas.

These schemas are used for adapter registration and management.
"""

from .registration import AdapterServiceRegistration

__all__ = [
    "AdapterServiceRegistration",
]
