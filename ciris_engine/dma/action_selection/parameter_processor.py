"""Parameter processing for Action Selection PDMA results."""

import logging
import re
from typing import Dict, Any, Union
from pydantic import ValidationError

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RecallParams,
    ForgetParams,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

logger = logging.getLogger(__name__)


class ActionParameterProcessor:
    """Processes and validates action parameters from LLM responses."""
    
    @staticmethod
    def process_action_parameters(
        llm_response: ActionSelectionResult,
        triaged_inputs: Dict[str, Any]
    ) -> ActionSelectionResult:
        """Process and validate action parameters from LLM response."""
        
        # Parse action parameters to correct type
        parsed_action_params = ActionParameterProcessor._parse_parameters_to_typed_model(
            llm_response.action_parameters,
            llm_response.selected_action
        )
        
        # Inject channel_id for SPEAK actions if available
        if llm_response.selected_action == HandlerActionType.SPEAK:
            parsed_action_params = ActionParameterProcessor._inject_channel_id(
                parsed_action_params, triaged_inputs
            )
        
        # Return updated result
        return ActionSelectionResult(
            selected_action=llm_response.selected_action,
            action_parameters=parsed_action_params,
            rationale=llm_response.rationale,
            confidence=getattr(llm_response, "confidence", None),
            raw_llm_response=getattr(llm_response, "raw_llm_response", None),
        )
    
    @staticmethod
    def _parse_parameters_to_typed_model(
        action_parameters: Union[Dict[str, Any], Any],
        action_type: HandlerActionType
    ) -> Union[Any, Dict[str, Any]]:
        """Parse action parameters dict into the appropriate Pydantic model."""
        
        if not isinstance(action_parameters, dict):
            return action_parameters
        
        param_map = {
            HandlerActionType.OBSERVE: ObserveParams,
            HandlerActionType.SPEAK: SpeakParams,
            HandlerActionType.TOOL: ToolParams,
            HandlerActionType.PONDER: PonderParams,
            HandlerActionType.REJECT: RejectParams,
            HandlerActionType.DEFER: DeferParams,
            HandlerActionType.MEMORIZE: MemorizeParams,
            HandlerActionType.RECALL: RecallParams,
            HandlerActionType.FORGET: ForgetParams,
        }
        
        param_class = param_map.get(action_type)
        if param_class:
            try:
                return param_class(**action_parameters)
            except ValidationError as ve:
                logger.warning(
                    f"Could not parse action_parameters dict into {param_class.__name__} for {action_type}: {ve}. Using raw dict."
                )
        
        return action_parameters
    
    @staticmethod
    def _inject_channel_id(
        action_params: Any,
        triaged_inputs: Dict[str, Any]
    ) -> Any:
        """Inject channel_id into SPEAK action parameters if available."""
        
        if not hasattr(action_params, "channel_id"):
            return action_params
        
        channel_id = ActionParameterProcessor._extract_channel_id(triaged_inputs)
        if channel_id and hasattr(action_params, "channel_id"):
            action_params.channel_id = channel_id
        
        return action_params
    
    @staticmethod
    def _extract_channel_id(triaged_inputs: Dict[str, Any]) -> str | None:
        """Extract channel_id from processing context."""
        processing_context = triaged_inputs.get("processing_context")
        if not processing_context:
            return None
        
        channel_id = None
        
        if (
            hasattr(processing_context, "identity_context")
            and processing_context.identity_context
        ):
            if (
                isinstance(processing_context.identity_context, str)
                and "channel" in processing_context.identity_context
            ):
                match = re.search(
                    r"channel is (\S+)", processing_context.identity_context
                )
                if match:
                    channel_id = match.group(1)

        if (
            not channel_id
            and hasattr(processing_context, "initial_task_context")
            and processing_context.initial_task_context
        ):
            if isinstance(processing_context.initial_task_context, dict):
                channel_id = processing_context.initial_task_context.get("channel_id")

        if (
            not channel_id
            and hasattr(processing_context, "system_snapshot")
            and processing_context.system_snapshot
        ):
            channel_id = getattr(
                processing_context.system_snapshot, "channel_id", None
            )

        if not channel_id and isinstance(processing_context, dict):
            channel_id = (
                (processing_context.get("identity_context", {}) or {}).get("channel_id")
                or (processing_context.get("initial_task_context", {}) or {}).get("channel_id")
                or processing_context.get("channel_id")
            )
        
        return channel_id