from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.processing_schemas_v1 import DMAResults, GuardrailResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import DeferParams, SpeakParams, PonderParams
from ciris_engine.utils import DEFAULT_WA
from ciris_engine.formatters.system_snapshot import format_system_snapshot
from ciris_engine.formatters.user_profiles import format_user_profiles
from ciris_engine.utils.task_formatters import format_task_context
from ciris_engine.processor.thought_escalation import escalate_due_to_guardrail
from pydantic import BaseModel
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GuardrailOrchestrator:
    def __init__(self, ethical_guardrails: EthicalGuardrails):
        self.ethical_guardrails = ethical_guardrails
        
    async def apply_guardrails(
        self,
        action_result: ActionSelectionResult,
        thought: Thought,
        dma_results_dict: Dict[str, Any]
    ) -> GuardrailResult:
        """Apply guardrails and handle overrides. Retries up to 3 times if guardrail fails."""
        
        # Skip guardrails for TASK_COMPLETE actions - they should proceed immediately
        if action_result.selected_action == HandlerActionType.TASK_COMPLETE:
            logger.debug(f"GuardrailOrchestrator: Skipping guardrails for TASK_COMPLETE action on thought {thought.thought_id}")
            return GuardrailResult(
                original_action=action_result,
                final_action=action_result,
                overridden=False,
                override_reason=None,
                epistemic_data=None,
            )
        
        # Parse the incoming dict into DMAResults model
        try:
            dma_results = DMAResults(**dma_results_dict)
        except Exception as e:
            logger.error(f"Failed to parse dma_results_dict into DMAResults model: {e}", exc_info=True)
            dma_results = DMAResults()

        # Inject channel_id for SPEAK actions before guardrail check
        if action_result.selected_action == HandlerActionType.SPEAK:
            params = action_result.action_parameters
            
            # Try to get channel_id from multiple sources
            channel_id = None
            
            # 1. From dma_results_dict processing_context
            if isinstance(dma_results_dict, dict) and 'processing_context' in dma_results_dict:
                proc_ctx = dma_results_dict['processing_context']
                if isinstance(proc_ctx, dict):
                    channel_id = proc_ctx.get('channel_id')
                    if not channel_id:
                        # Check system_snapshot within processing_context
                        sys_snap = proc_ctx.get('system_snapshot', {})
                        if isinstance(sys_snap, dict):
                            channel_id = sys_snap.get('channel_id')
            
            # 2. From thought context
            if not channel_id and hasattr(thought, 'context') and isinstance(thought.context, dict):
                channel_id = thought.context.get('channel_id')
            
            # 3. From identity_context parsing
            if not channel_id and isinstance(dma_results_dict, dict):
                identity_ctx = dma_results_dict.get('identity_context')
                if isinstance(identity_ctx, str) and 'channel is' in identity_ctx:
                    import re
                    match = re.search(r'channel is (\S+)', identity_ctx)
                    if match:
                        channel_id = match.group(1)
            
            # 4. From environment variable as last resort
            if not channel_id:
                import os
                channel_id = os.getenv('DISCORD_CHANNEL_ID')
            
            # Inject channel_id if found
            if channel_id:
                if isinstance(params, dict):
                    params['channel_id'] = channel_id
                elif isinstance(params, SpeakParams):
                    params.channel_id = channel_id
                action_result.action_parameters = params
                logger.debug(f"Injected channel_id={channel_id} into SPEAK parameters")
            else:
                logger.error("Failed to find channel_id from any source!")
        
        # ... rest of the method remains the same
            # Retry guardrail check up to 3 times if it fails
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                passes_guardrail, reason, epistemic_data = await self.ethical_guardrails.check_action_output_safety(action_result)
                if passes_guardrail:
                    break
                logger.info(f"Guardrail failed attempt {attempt} for thought ID {thought.thought_id}: {reason}")
                if attempt < max_retries:
                    continue
                # Only proceed to override after final failed attempt

            override_action_result = None
            if not passes_guardrail:
                logger.info(f"Guardrail failed for thought ID {thought.thought_id}: {reason}. Overriding action to PONDER.")

                # Create ponder questions based on the guardrail failure
                ponder_questions = [
                    f"Why did the guardrail fail with reason: {reason}?",
                    "What alternative approach would satisfy the epistemic constraints?",
                    "How can I reformulate my response to align with CIRIS values?"
                ]

                # Add specific questions based on epistemic data
                if epistemic_data:
                    if epistemic_data.get('entropy', 0) > self.ethical_guardrails.entropy_threshold:
                        ponder_questions.append("How can I reduce the entropy/chaos in my response?")
                    if epistemic_data.get('coherence', 1) < self.ethical_guardrails.coherence_threshold:
                        ponder_questions.append("How can I better align my response with CIRIS principles?")
                    if 'optimization_veto' in epistemic_data:
                        veto = epistemic_data['optimization_veto']
                        if veto.get('decision') in ['abort', 'defer']:
                            ponder_questions.append(f"Optimization concern: {veto.get('justification')} - How to address this?")
                    if 'epistemic_humility' in epistemic_data:
                        humility = epistemic_data['epistemic_humility']
                        if humility.get('recommended_action') in ['abort', 'defer']:
                            ponder_questions.extend(humility.get('identified_uncertainties', []))

                ponder_params = PonderParams(questions=ponder_questions[:5])  # Limit to 5 questions

                override_action_result = ActionSelectionResult(
                    selected_action=HandlerActionType.PONDER,
                    action_parameters=ponder_params.model_dump(mode='json'),
                    rationale=f"Original action '{action_result.selected_action.value}' failed guardrails. Pondering to find aligned approach. Reason: {reason}",
                    confidence=0.3,  # Low confidence due to guardrail failure
                    raw_llm_response=action_result.raw_llm_response
                )

                logger.info(f"Guardrail triggered PONDER for thought {thought.thought_id}: {reason}")

            final_action = override_action_result if override_action_result else action_result

            # Normalize action_parameters for all main action types before dispatch
            if final_action.selected_action == HandlerActionType.SPEAK:
                params = final_action.action_parameters
                if isinstance(params, dict):
                    final_action.action_parameters = SpeakParams(**params)
            elif final_action.selected_action == HandlerActionType.DEFER:
                params = final_action.action_parameters
                if isinstance(params, dict):
                    final_action.action_parameters = DeferParams(**params)
            elif final_action.selected_action == HandlerActionType.PONDER:
                params = final_action.action_parameters
                if isinstance(params, dict):
                    final_action.action_parameters = PonderParams(**params)

            return GuardrailResult(
                original_action=action_result,
                final_action=final_action,
                overridden=not passes_guardrail,
                override_reason=reason if not passes_guardrail else None,
                epistemic_data=epistemic_data,
            )
