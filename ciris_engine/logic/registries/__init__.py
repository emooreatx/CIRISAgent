"""
CIRIS Engine Registry System

Provides unified registration and discovery for services, adapters, and tools
with priority-based fallbacks and circuit breaker patterns for resilience.
"""

from .base import Priority, SelectionStrategy, ServiceProvider, ServiceRegistry
from .circuit_breaker import CircuitBreaker

__all__ = ["ServiceRegistry", "Priority", "SelectionStrategy", "ServiceProvider", "CircuitBreaker"]
