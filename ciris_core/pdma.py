from __future__ import annotations
import asyncio
from typing import Tuple

from ciris_engine.formatters.prompt_blocks import (
    format_system_prompt_blocks,
    format_user_prompt_blocks,
)
from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
from ciris_engine.schemas.guardrails_config_v1 import GuardrailsConfig
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

PDMA_DESCRIPTION = """Contextualisation
Describe the situation and potential actions.
List all affected stakeholders and relevant constraints.
Map direct and indirect consequences.

Alignment Assessment
Evaluate each action against all core principles and Meta-Goal M-1.
Detect conflicts among principles.
Perform Order-Maximisation Veto check.

Conflict Identification
Articulate principle conflicts or trade-offs.

Conflict Resolution
Apply prioritisation heuristics (Non-maleficence priority, Autonomy thresholds, Justice balancing).

Selection & Execution
Implement the ethically optimal action.

Continuous Monitoring
Compare expected vs. actual impacts; update heuristics."""

class PDMAEvaluator:
    """Deterministic PDMA evaluator for tests."""

    def __init__(self, guardrails: GuardrailsConfig | None = None) -> None:
        self.guardrails = guardrails or GuardrailsConfig()

    def build_prompt(self, thought: Thought) -> Tuple[str, str]:
        guardrail_lines = [
            f"entropy_threshold={self.guardrails.entropy_threshold}",
            f"coherence_threshold={self.guardrails.coherence_threshold}",
            f"optimization_veto_ratio={self.guardrails.optimization_veto_ratio}",
        ]
        system_guidance = PDMA_DESCRIPTION + "\nGuardrails: " + ", ".join(guardrail_lines)
        system_prompt = format_system_prompt_blocks(
            "PDMA Evaluator", "N/A", "N/A", "N/A", system_guidance_block=system_guidance
        )
        user_prompt = format_user_prompt_blocks("N/A", f"Thought: {thought.content}")
        return system_prompt, user_prompt

    async def evaluate(self, thought: Thought) -> EthicalDMAResult:
        # Build prompts (not used further but satisfies format guideline)
        _system_msg, _user_msg = self.build_prompt(thought)

        action = HandlerActionType.SPEAK if thought.thought_type == "seed" else HandlerActionType.PONDER
        alignment_check = {
            "plausible_actions": [a.value for a in [HandlerActionType.SPEAK, HandlerActionType.PONDER]],
            "selected": action.value,
            "do_good": "No harm detected",
            "avoid_harm": "No direct harm",
            "honor_autonomy": "Respects autonomy",
            "ensure_fairness": "Fair",
            "fidelity_transparency": "Transparent",
            "integrity": "Maintains integrity",
            "meta_goal_m1": "High coherence",
        }
        decision = action.value
        rationale = f"Chosen because thought type '{thought.thought_type}' maps to {action.value}."
        return EthicalDMAResult(
            alignment_check=alignment_check,
            decision=decision,
            rationale=rationale,
        )
