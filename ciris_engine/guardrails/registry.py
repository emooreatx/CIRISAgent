from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ciris_engine.registries.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from .interface import GuardrailInterface

@dataclass
class GuardrailEntry:
    name: GuardrailInterface
    guardrail: GuardrailInterface
    priority: GuardrailInterface = 0
    enabled: GuardrailInterface = True
    circuit_breaker: CircuitBreaker | None = None

class GuardrailRegistry:
    """Registry for dynamic guardrail management."""

    def __init__(self) -> None:
        self._entries: Dict[str, GuardrailEntry] = {}

    def register_guardrail(
        self,
        name: str,
        guardrail: GuardrailInterface,
        priority: int = 0,
        enabled: bool = True,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Register a guardrail with priority."""
        cb = CircuitBreaker(name, circuit_breaker_config or CircuitBreakerConfig())
        entry = GuardrailEntry(name, guardrail, priority, enabled, cb)
        self._entries[name] = entry

    def get_guardrails(self) -> List[GuardrailEntry]:
        """Return enabled guardrails ordered by priority."""
        return sorted(
            [e for e in self._entries.values() if e.enabled],
            key=lambda e: e.priority,
        )

    def set_enabled(self, name: str, enabled: bool) -> None:
        if name in self._entries:
            self._entries[name].enabled = enabled
