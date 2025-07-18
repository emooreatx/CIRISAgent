"""
Circuit Breaker Pattern Implementation

Provides fault tolerance by monitoring service failures and temporarily
disabling failing services to prevent cascading failures.
"""

import time
import logging
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open and service is unavailable"""

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Service disabled due to failures
    HALF_OPEN = "half_open"  # Testing if service has recovered

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    timeout_duration: float = 30.0

class CircuitBreaker:
    """
    Circuit breaker implementation for service resilience.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service disabled, requests fail fast
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None) -> None:
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

        logger.debug(f"Circuit breaker '{name}' initialized")

    def is_available(self) -> bool:
        """Check if the service is available for requests"""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if (self.last_failure_time and
                time.time() - self.last_failure_time >= self.config.recovery_timeout):
                self._transition_to_half_open()
                return True
            return False

        # CircuitState.HALF_OPEN case
        # Allow limited requests in half-open state
        return True

    def check_and_raise(self) -> None:
        """Check if service is available, raise CircuitBreakerError if not"""
        if not self.is_available():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is {self.state.value}, service unavailable"
            )

    def record_success(self) -> None:
        """Record a successful operation"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to_open()

    def _transition_to_open(self) -> None:
        """Transition to OPEN state (service disabled)"""
        self.state = CircuitState.OPEN
        self.success_count = 0
        logger.warning(f"Circuit breaker '{self.name}' opened due to {self.failure_count} failures")

    def _transition_to_half_open(self) -> None:
        """Transition to HALF_OPEN state (testing recovery)"""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' transitioning to half-open for recovery testing")

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state (normal operation)"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        logger.info(f"Circuit breaker '{self.name}' closed - service recovered")

    def get_stats(self) -> dict[str, Any]:
        """Get current circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time
        }

    def reset(self) -> None:
        """Reset circuit breaker to initial state"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker '{self.name}' manually reset")
