"""Faculty integration for Action Selection PDMA."""

import logging
from typing import Dict, Any, Optional
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.protocols.faculties import EpistemicFaculty

logger = logging.getLogger(__name__)


class FacultyIntegration:
    """Handles epistemic faculty integration for enhanced action selection."""
    
    def __init__(self, faculties: Dict[str, EpistemicFaculty]):
        self.faculties = faculties
    
    async def apply_faculties_to_content(
        self,
        content: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Apply available epistemic faculties to content."""
        results = {}
        for name, faculty in self.faculties.items():
            try:
                result = await faculty.evaluate(content, context)
                results[name] = result
            except Exception as e:
                logger.warning(f"Faculty {name} evaluation failed: {e}")
        return results
    
    def build_faculty_insights_string(self, faculty_results: Dict[str, Any]) -> str:
        """Build a formatted string of faculty insights for prompt injection."""
        if not faculty_results:
            return ""
        
        faculty_insights_str = "\n\nEPISTEMIC FACULTY INSIGHTS:\n"
        for faculty_name, result in faculty_results.items():
            faculty_insights_str += f"- {faculty_name}: {result}\n"
        faculty_insights_str += "\nConsider these faculty evaluations in your decision-making process.\n"
        
        return faculty_insights_str
    
    async def enhance_evaluation_with_faculties(
        self,
        original_thought: Thought,
        triaged_inputs: Dict[str, Any],
        guardrail_failure_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enhance triaged inputs with faculty evaluations."""
        
        # Apply faculties to the thought content
        context = {
            **(guardrail_failure_context or {}),
            "evaluation_context": "faculty_enhanced_action_selection",
            "thought_metadata": {
                "thought_id": original_thought.thought_id,
                "thought_type": original_thought.thought_type,
                "source_task_id": original_thought.source_task_id
            }
        }
        
        faculty_results = await self.apply_faculties_to_content(
            content=str(original_thought.content),
            context=context
        )
        
        logger.debug(f"Faculty evaluation results for thought {original_thought.thought_id}: {faculty_results}")
        
        # Enhance triaged inputs with faculty insights
        enhanced_inputs = {
            **triaged_inputs,
            "faculty_evaluations": faculty_results,
            "faculty_enhanced": True
        }
        
        if guardrail_failure_context:
            enhanced_inputs["guardrail_context"] = guardrail_failure_context
        
        return enhanced_inputs
    
    def add_faculty_metadata_to_result(
        self,
        result: ActionSelectionResult,
        faculty_enhanced: bool = False,
        recursive_evaluation: bool = False
    ) -> ActionSelectionResult:
        """Add faculty-related metadata to the action selection result."""
        
        if not faculty_enhanced:
            return result
        
        metadata_suffix = "\n\nNote: This decision incorporated insights from epistemic faculties"
        if recursive_evaluation:
            metadata_suffix += " through recursive evaluation due to guardrail failure"
        metadata_suffix += "."
        
        updated_rationale = result.rationale + metadata_suffix
        
        return ActionSelectionResult(
            selected_action=result.selected_action,
            action_parameters=result.action_parameters,
            rationale=updated_rationale,
            confidence=result.confidence,
            raw_llm_response=result.raw_llm_response,
            resource_usage=result.resource_usage
        )