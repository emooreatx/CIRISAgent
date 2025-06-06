from __future__ import annotations

import logging
import re
import time
from collections import deque
from typing import Any, Dict, Deque, Tuple

logger = logging.getLogger(__name__)


class SecurityFilter:
    """Sanitize telemetry metrics to prevent sensitive data leaks."""

    def __init__(
        self,
        bounds: Dict[str, Tuple[float, float]] | None = None,
        rate_limits: Dict[str, Tuple[int, float]] | None = None,
    ) -> None:
        self.bounds = bounds or {}
        self.rate_limits = rate_limits or {}
        self._history: Dict[str, Deque[float]] = {
            name: deque() for name in self.rate_limits
        }

    def sanitize(self, metric_name: str, value: Any) -> Tuple[str, Any] | None:
        if not isinstance(metric_name, str):
            return None

        # Rate limiting
        if not self._check_rate_limit(metric_name):
            logger.debug("Metric %s rate limited", metric_name)
            return None

        if isinstance(value, str):
            if self._contains_pii(value):
                logger.warning("PII detected in metric %s", metric_name)
                return None
            if metric_name.endswith("error"):
                value = self._sanitize_error(value)
                return metric_name, value
            else:
                return None

        if isinstance(value, (int, float)):
            if not self._validate_bounds(metric_name, float(value)):
                logger.warning("Metric %s out of bounds", metric_name)
                return None
            return metric_name, float(value)

        return None

    def _contains_pii(self, text: str) -> bool:
        email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
        ssn = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        phone = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
        return bool(email.search(text) or ssn.search(text) or phone.search(text))

    def _sanitize_error(self, message: str) -> str:
        message = re.sub(r"/[^\s]+", "[REDACTED]", message)
        message = re.sub(r"\b0x[0-9a-fA-F]+\b", "0xXXXX", message)
        return message[:200]

    def _validate_bounds(self, name: str, value: float) -> bool:
        if name in self.bounds:
            low, high = self.bounds[name]
            if value < low or value > high:
                return False
        return True

    def _check_rate_limit(self, name: str) -> bool:
        if name not in self.rate_limits:
            return True
        limit, period = self.rate_limits[name]
        history = self._history.setdefault(name, deque())
        now = time.monotonic()
        while history and now - history[0] > period:
            history.popleft()
        if len(history) >= limit:
            return False
        history.append(now)
        return True
