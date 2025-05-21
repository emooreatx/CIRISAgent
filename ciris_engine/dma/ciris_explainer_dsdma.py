import logging
from typing import Dict, Any, List

from .dsdma_base import BaseDSDMA, InstructorRetryException
from ciris_engine.core.agent_processing_queue import ProcessingQueueItem
from ciris_engine.core.dma_results import DSDMAResult
from ciris_engine.utils.task_formatters import format_task_context
from ciris_engine.formatters.system_snapshot import format_system_snapshot
from ciris_engine.formatters.user_profiles import format_user_profiles
from ciris_engine.formatters.prompt_blocks import (
    format_parent_task_chain,
    format_thoughts_chain,
    format_user_prompt_blocks,
)
from ciris_engine.formatters.escalation import get_escalation_guidance

logger = logging.getLogger(__name__)


class CIRISExplainerDSDMA(BaseDSDMA):
    """Domain-specific DMA with canonical CIRIS explainer template."""

    DEFAULT_TEMPLATE = """=== Task History ===
{task_history_block}

=== CIRIS System Guidance ===
You are a CIRIS Explainer Agent. Your role is to evaluate thoughts explicitly according to the CIRIS Covenant, which includes:

- Coherence: maintaining logical and ethical consistency.
- Integrity: ensuring reliability and honesty.
- Adaptive Ethical Reasoning: dynamically applying principles contextually.

Clearly explain and evaluate thoughts strictly through CIRIS reasoning and terminology.

=== Escalation Guidance ===
{escalation_guidance_block}

=== System Snapshot ===
{system_snapshot_block}

=== User Profiles ===
{user_profiles_block}
"""

    async def evaluate_thought(
        self, thought_item: ProcessingQueueItem, current_context: Dict[str, Any]
    ) -> DSDMAResult:
        # Extract context blocks
        task_history_block = format_task_context(
            current_context.get("current_task", {}),
            current_context.get("recent_actions", []),
            current_context.get("completed_tasks", []),
        )

        escalation_block = get_escalation_guidance(
            current_context.get("actions_taken", 0),
            current_context.get("max_actions", 7),
        )

        system_snapshot_block = format_system_snapshot(
            current_context.get("system_snapshot", {})
        )

        user_profiles_block = format_user_profiles(
            current_context.get("user_profiles", {})
        )

        parent_tasks_block = format_parent_task_chain(
            current_context.get("parent_tasks", [])
        )

        thoughts_chain: List[Dict[str, Any]] = current_context.get("thoughts_chain", [])
        if not thoughts_chain:
            thoughts_chain = [{"content": str(thought_item.content)}]
        else:
            thoughts_chain.append({"content": str(thought_item.content)})

        thoughts_chain_block = format_thoughts_chain(thoughts_chain)

        system_message = self.DEFAULT_TEMPLATE.format(
            task_history_block=task_history_block,
            escalation_guidance_block=escalation_block,
            system_snapshot_block=system_snapshot_block,
            user_profiles_block=user_profiles_block,
        )

        user_message = format_user_prompt_blocks(
            parent_tasks_block,
            thoughts_chain_block,
            None,
        )

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]

        try:
            llm_eval_data: BaseDSDMA.LLMOutputForDSDMA = await self.aclient.chat.completions.create(
                model=self.model_name,
                response_model=BaseDSDMA.LLMOutputForDSDMA,
                messages=messages,
                max_tokens=512,
            )

            result = DSDMAResult(
                domain_name=self.domain_name,
                domain_alignment_score=min(max(llm_eval_data.domain_alignment_score, 0.0), 1.0),
                recommended_action=llm_eval_data.recommended_action,
                flags=llm_eval_data.flags,
                reasoning=llm_eval_data.reasoning,
                domain_specific_output={},
            )
            if hasattr(llm_eval_data, "_raw_response"):
                result.raw_llm_response = str(llm_eval_data._raw_response)
            return result
        except InstructorRetryException as e_instr:
            error_detail = e_instr.errors() if hasattr(e_instr, "errors") else str(e_instr)
            logger.error(
                f"CIRISExplainerDSDMA {self.domain_name} InstructorRetryException for thought {thought_item.thought_id}: {error_detail}",
                exc_info=True,
            )
            return DSDMAResult(
                domain_name=self.domain_name,
                domain_alignment_score=0.0,
                recommended_action=None,
                flags=["Instructor_ValidationError"],
                reasoning=f"Failed DSDMA evaluation via instructor due to validation error: {error_detail}",
                raw_llm_response=f"InstructorRetryException: {error_detail}",
            )
        except Exception as e:
            logger.error(
                f"CIRISExplainerDSDMA {self.domain_name} evaluation failed for thought ID {thought_item.thought_id}: {e}",
                exc_info=True,
            )
            return DSDMAResult(
                domain_name=self.domain_name,
                domain_alignment_score=0.0,
                recommended_action=None,
                flags=["LLM_Error_Instructor"],
                reasoning=f"Failed DSDMA evaluation via instructor: {str(e)}",
                raw_llm_response=f"Exception: {str(e)}",
            )
