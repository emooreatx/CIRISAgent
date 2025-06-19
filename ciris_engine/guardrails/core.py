from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from ciris_engine.schemas.config_schemas_v1 import GuardrailsConfig, DEFAULT_OPENAI_MODEL_NAME
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.guardrails_schemas_v1 import (
    GuardrailCheckResult,
    GuardrailStatus,
)
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.faculties.epistemic import (
    calculate_epistemic_values,
    evaluate_optimization_veto,
    evaluate_epistemic_humility,
)
from ciris_engine.protocols.services import LLMService

from .interface import GuardrailInterface

logger = logging.getLogger(__name__)


class _BaseGuardrail(GuardrailInterface):
    def __init__(
        self,
        service_registry: ServiceRegistry,
        config: GuardrailsConfig,
        model_name: str = DEFAULT_OPENAI_MODEL_NAME,
        sink: Any = None,
    ) -> None:
        self.service_registry = service_registry
        self.config = config
        self.model_name = model_name
        self.sink = sink

    async def _get_sink(self) -> Any:
        """Get the multi-service sink for centralized LLM calls with circuit breakers."""
        if self.sink:
            return self.sink
        # Fallback to creating a bus manager if not provided
        from ciris_engine.message_buses import BusManager
        return BusManager(self.service_registry)


class EntropyGuardrail(_BaseGuardrail):
    async def check(self, action: ActionSelectionResult, context: Dict[str, Any]) -> GuardrailCheckResult:
        ts = datetime.now(timezone.utc).isoformat()
        if action.selected_action != HandlerActionType.SPEAK:
            return GuardrailCheckResult(
                status=GuardrailStatus.PASSED,
                passed=True,
                check_timestamp=ts,
            )
        sink = await self._get_sink()
        if not sink:
            return GuardrailCheckResult(
                status=GuardrailStatus.WARNING,
                passed=True,
                reason="Sink service unavailable",
                check_timestamp=ts,
            )
        text = ""
        params = action.action_parameters
        if isinstance(params, dict):
            text = params.get("content", "")
        elif hasattr(params, "content"):
            text = getattr(params, "content", "")
        if not text:
            return GuardrailCheckResult(
                status=GuardrailStatus.PASSED,
                passed=True,
                reason="No content to evaluate",
                check_timestamp=ts,
            )
        epi = await calculate_epistemic_values(text, sink, self.model_name)
        entropy = epi.get("entropy", 0.0)
        passed = entropy <= self.config.entropy_threshold
        status = GuardrailStatus.PASSED if passed else GuardrailStatus.FAILED
        reason = None
        if not passed:
            reason = (
                f"Entropy {entropy:.2f} > threshold {self.config.entropy_threshold:.2f}"
            )
        return GuardrailCheckResult(
            status=status,
            passed=passed,
            reason=reason,
            epistemic_data={"entropy": entropy},
            entropy_check={"entropy": entropy, "threshold": self.config.entropy_threshold},
            entropy_score=entropy,
            check_timestamp=ts,
        )


class CoherenceGuardrail(_BaseGuardrail):
    async def check(self, action: ActionSelectionResult, context: Dict[str, Any]) -> GuardrailCheckResult:
        ts = datetime.now(timezone.utc).isoformat()
        if action.selected_action != HandlerActionType.SPEAK:
            return GuardrailCheckResult(status=GuardrailStatus.PASSED, passed=True, check_timestamp=ts)
        sink = await self._get_sink()
        if not sink:
            return GuardrailCheckResult(status=GuardrailStatus.WARNING, passed=True, reason="Sink service unavailable", check_timestamp=ts)
        text = ""
        params = action.action_parameters
        if isinstance(params, dict):
            text = params.get("content", "")
        elif hasattr(params, "content"):
            text = getattr(params, "content", "")
        if not text:
            return GuardrailCheckResult(status=GuardrailStatus.PASSED, passed=True, reason="No content to evaluate", check_timestamp=ts)
        epi = await calculate_epistemic_values(text, sink, self.model_name)
        coherence = epi.get("coherence", 1.0)
        passed = coherence >= self.config.coherence_threshold
        status = GuardrailStatus.PASSED if passed else GuardrailStatus.FAILED
        reason = None
        if not passed:
            reason = (
                f"Coherence {coherence:.2f} < threshold {self.config.coherence_threshold:.2f}"
            )
        return GuardrailCheckResult(
            status=status,
            passed=passed,
            reason=reason,
            epistemic_data={"coherence": coherence},
            coherence_check={"coherence": coherence, "threshold": self.config.coherence_threshold},
            coherence_score=coherence,
            check_timestamp=ts,
        )


class OptimizationVetoGuardrail(_BaseGuardrail):
    async def check(self, action: ActionSelectionResult, context: Dict[str, Any]) -> GuardrailCheckResult:
        ts = datetime.now(timezone.utc).isoformat()
        sink = await self._get_sink()
        if not sink:
            return GuardrailCheckResult(status=GuardrailStatus.WARNING, passed=True, reason="Sink service unavailable", check_timestamp=ts)
        result = await evaluate_optimization_veto(action, sink, self.model_name)
        passed = result.decision not in {"abort", "defer"} and result.entropy_reduction_ratio < self.config.optimization_veto_ratio
        status = GuardrailStatus.PASSED if passed else GuardrailStatus.FAILED
        reason = None
        if not passed:
            reason = f"Optimization veto triggered: {result.justification}"
        return GuardrailCheckResult(
            status=status,
            passed=passed,
            reason=reason,
            epistemic_data=result.model_dump(),
            optimization_veto_check=result.model_dump(),
            check_timestamp=ts,
        )


class EpistemicHumilityGuardrail(_BaseGuardrail):
    async def check(self, action: ActionSelectionResult, context: Dict[str, Any]) -> GuardrailCheckResult:
        ts = datetime.now(timezone.utc).isoformat()
        sink = await self._get_sink()
        if not sink:
            return GuardrailCheckResult(status=GuardrailStatus.WARNING, passed=True, reason="Sink service unavailable", check_timestamp=ts)
        result = await evaluate_epistemic_humility(action, sink, self.model_name)
        passed = result.recommended_action not in {"abort", "defer", "ponder"}
        status = GuardrailStatus.PASSED if passed else GuardrailStatus.FAILED
        reason = None
        if not passed:
            reason = f"Epistemic humility request: {result.recommended_action}"
        return GuardrailCheckResult(
            status=status,
            passed=passed,
            reason=reason,
            epistemic_data=result.model_dump(),
            epistemic_humility_check=result.model_dump(),
            check_timestamp=ts,
        )
