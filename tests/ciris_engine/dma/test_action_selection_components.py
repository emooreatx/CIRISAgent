"""Tests for Action Selection PDMA components."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

from ciris_engine.dma.action_selection.context_builder import ActionSelectionContextBuilder
from ciris_engine.dma.action_selection.special_cases import ActionSelectionSpecialCases
from ciris_engine.dma.action_selection.parameter_processor import ActionParameterProcessor
from ciris_engine.dma.action_selection.faculty_integration import FacultyIntegration
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult,
    CSDMAResult,
    DSDMAResult,
    ActionSelectionResult,
)
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtType
from ciris_engine.schemas.action_params_v1 import SpeakParams, PonderParams
from datetime import datetime
from ciris_engine.protocols.faculties import EpistemicFaculty
from pydantic import BaseModel


class MockFaculty:
    """Mock epistemic faculty for testing."""
    
    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        class MockResult(BaseModel):
            score: float = 0.8
            insight: str = f"Analysis of: {content[:20]}..."
        
        return MockResult()


class TestActionSelectionContextBuilder:
    """Test the context builder component."""
    
    @pytest.fixture
    def mock_prompts(self):
        return {
            "system_header": "You are a CIRIS action selector",
            "decision_format": "Return JSON with selected action",
            "closing_reminder": "Follow CIRIS principles",
            "action_parameter_schemas": "SPEAK: {content: string}",
            "csdma_ambiguity_guidance": "If CSDMA flagged ambiguity...",
            "action_params_speak_csdma_guidance": "Use content field for speak",
            "final_ponder_advisory": "FINAL ATTEMPT: Choose SPEAK or DEFER"
        }
    
    @pytest.fixture
    def context_builder(self, mock_prompts):
        return ActionSelectionContextBuilder(mock_prompts)
    
    @pytest.fixture
    def mock_triaged_inputs(self):
        return {
            "original_thought": Thought(
                thought_id="test-123",
                content="Test thought content",
                source_task_id="test-task-123",
                thought_type=ThoughtType.STANDARD,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                ponder_notes=["Previous question 1", "Previous question 2"]
            ),
            "ethical_pdma_result": EthicalDMAResult(
                alignment_check={"do_good": "aligned", "conflicts": "none"},
                decision="approved",
                rationale="Ethical evaluation passed"
            ),
            "csdma_result": CSDMAResult(
                plausibility_score=0.85,
                flags=["minor_ambiguity"],
                reasoning="Generally plausible with minor issues"
            ),
            "dsdma_result": DSDMAResult(
                domain="test_domain",
                score=0.9,
                flags=[],
                reasoning="Domain appropriate",
                recommended_action="proceed"
            ),
            "current_thought_depth": 1,
            "max_rounds": 3,
            "permitted_actions": [
                HandlerActionType.SPEAK,
                HandlerActionType.PONDER,
                HandlerActionType.DEFER
            ]
        }
    
    def test_build_main_user_content(self, context_builder, mock_triaged_inputs):
        """Test building main user content for LLM evaluation."""
        
        content = context_builder.build_main_user_content(mock_triaged_inputs)
        
        # Check that key elements are present
        assert "Test thought content" in content
        assert "speak, ponder, defer" in content
        assert "Ethical PDMA Stance: approved" in content
        assert "CSDMA Output: Plausibility 0.85" in content
        assert "DSDMA (test_domain)" in content
        assert "Previous question 1" in content
        assert "pondered 1 time(s)" in content
    
    def test_build_main_user_content_no_ponder_notes(self, context_builder, mock_triaged_inputs):
        """Test content building when there are no ponder notes."""
        
        mock_triaged_inputs["original_thought"].ponder_notes = []
        mock_triaged_inputs["current_thought_depth"] = 0
        
        content = context_builder.build_main_user_content(mock_triaged_inputs)
        
        assert "Previous question" not in content
        assert "Test thought content" in content
    
    def test_build_main_user_content_final_attempt(self, context_builder, mock_triaged_inputs):
        """Test content building for final attempt."""
        
        mock_triaged_inputs["current_thought_depth"] = 2  # max_rounds - 1
        
        content = context_builder.build_main_user_content(
            mock_triaged_inputs, 
            agent_name="test"
        )
        
        assert "FINAL ATTEMPT" in content
    
    def test_build_main_user_content_startup_thought(self, context_builder, mock_triaged_inputs):
        """Test content building for startup thoughts."""
        
        mock_triaged_inputs["original_thought"].thought_type = "startup_meta"
        
        content = context_builder.build_main_user_content(mock_triaged_inputs)
        
        assert "CRITICAL STARTUP DIRECTIVE" in content
    
    def test_get_permitted_actions_default(self, context_builder):
        """Test getting permitted actions with defaults."""
        
        triaged_inputs = {
            "original_thought": Thought(
                thought_id="test", 
                content="test",
                source_task_id="test-task",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )
        }
        
        actions = context_builder._get_permitted_actions(triaged_inputs)
        
        # Should include all default actions
        assert HandlerActionType.SPEAK in actions
        assert HandlerActionType.PONDER in actions
        assert HandlerActionType.TOOL in actions
        assert len(actions) == 10  # All default actions
    
    def test_get_permitted_actions_custom(self, context_builder):
        """Test getting custom permitted actions."""
        
        custom_actions = [HandlerActionType.SPEAK, HandlerActionType.DEFER]
        triaged_inputs = {
            "original_thought": Thought(
                thought_id="test", 
                content="test",
                source_task_id="test-task",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ),
            "permitted_actions": custom_actions
        }
        
        actions = context_builder._get_permitted_actions(triaged_inputs)
        
        assert actions == custom_actions
    
    def test_get_available_tools_str(self, context_builder):
        """Test getting available tools string."""
        
        # The current implementation returns empty string because it can't get tools synchronously
        # The dynamic instruction generator handles this better
        permitted_actions = [HandlerActionType.TOOL, HandlerActionType.SPEAK]
        
        tools_str = context_builder._get_available_tools_str(permitted_actions)
        
        # For now, this returns empty string due to async/sync limitations
        assert tools_str == ""
    
    def test_get_available_tools_str_no_tool_action(self, context_builder):
        """Test tools string when TOOL action not permitted."""
        
        permitted_actions = [HandlerActionType.SPEAK, HandlerActionType.PONDER]
        
        tools_str = context_builder._get_available_tools_str(permitted_actions)
        
        assert tools_str == ""


class TestActionSelectionSpecialCases:
    """Test the special cases handler component."""
    
    @pytest.fixture
    def mock_thought(self):
        return Thought(
            thought_id="test-special",
            content="Test content",
            source_task_id="test-task-123",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
    
    @pytest.mark.asyncio
    async def test_handle_ponder_force(self, mock_thought):
        """Test handling forced ponder case."""
        
        # Mock processing context with ponder keyword
        mock_context = MagicMock()
        mock_context.initial_task_context.content = "ponder"
        
        triaged_inputs = {
            "original_thought": mock_thought,
            "processing_context": mock_context
        }
        
        result = await ActionSelectionSpecialCases.handle_ponder_force(triaged_inputs)
        
        assert result is not None
        assert result.selected_action == HandlerActionType.PONDER
        assert isinstance(result.action_parameters, PonderParams)
        assert "Forced" in result.rationale and "ponder" in result.rationale.lower()
    
    @pytest.mark.asyncio
    async def test_handle_ponder_force_no_keyword(self, mock_thought):
        """Test ponder force when keyword not present."""
        
        mock_context = MagicMock()
        mock_context.initial_task_context.content = "normal message"
        
        triaged_inputs = {
            "original_thought": mock_thought,
            "processing_context": mock_context
        }
        
        result = await ActionSelectionSpecialCases.handle_ponder_force(triaged_inputs)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_handle_ponder_force_no_context(self, mock_thought):
        """Test ponder force with no processing context."""
        
        triaged_inputs = {
            "original_thought": mock_thought,
            "processing_context": None
        }
        
        result = await ActionSelectionSpecialCases.handle_ponder_force(triaged_inputs)
        
        assert result is None
    
    @patch('ciris_engine.dma.action_selection.special_cases.ActionSelectionSpecialCases._is_wakeup_task')
    @pytest.mark.asyncio
    async def test_handle_wakeup_task_speak_requirement(self, mock_is_wakeup, mock_thought):
        """Test wakeup task SPEAK requirement handling."""
        
        mock_is_wakeup.return_value = True
        
        # Mock LLM response that selected TASK_COMPLETE
        mock_llm_response = MagicMock()
        mock_llm_response.selected_action = HandlerActionType.TASK_COMPLETE
        
        triaged_inputs = {
            "original_thought": mock_thought,
            "llm_response_internal": mock_llm_response
        }
        
        with patch('ciris_engine.dma.action_selection.special_cases.ActionSelectionSpecialCases._task_has_successful_speak', return_value=False):
            result = await ActionSelectionSpecialCases.handle_wakeup_task_speak_requirement(triaged_inputs)
        
        assert result is not None
        assert result.selected_action == HandlerActionType.PONDER
        assert "wakeup step requires a SPEAK action" in result.action_parameters.questions[0]
    
    @patch('ciris_engine.dma.action_selection.special_cases.ActionSelectionSpecialCases._is_wakeup_task')
    @pytest.mark.asyncio
    async def test_handle_wakeup_task_not_wakeup(self, mock_is_wakeup, mock_thought):
        """Test handling when task is not a wakeup task."""
        
        mock_is_wakeup.return_value = False
        
        triaged_inputs = {
            "original_thought": mock_thought
        }
        
        result = await ActionSelectionSpecialCases.handle_wakeup_task_speak_requirement(triaged_inputs)
        
        assert result is None
    
    @patch('ciris_engine.persistence')
    def test_is_wakeup_task_with_parent(self, mock_persistence):
        """Test wakeup task detection with WAKEUP_ROOT parent."""
        
        mock_task = MagicMock()
        mock_task.parent_task_id = "WAKEUP_ROOT"
        mock_persistence.get_task_by_id.return_value = mock_task
        
        result = ActionSelectionSpecialCases._is_wakeup_task("test-task")
        
        assert result is True
    
    @patch('ciris_engine.persistence')
    def test_is_wakeup_task_with_step_type(self, mock_persistence):
        """Test wakeup task detection with step_type context."""
        
        mock_task = MagicMock()
        mock_task.parent_task_id = "OTHER_PARENT"
        mock_task.context = {"step_type": "wakeup_step"}
        mock_persistence.get_task_by_id.return_value = mock_task
        
        result = ActionSelectionSpecialCases._is_wakeup_task("test-task")
        
        assert result is True
    
    @patch('ciris_engine.persistence')
    def test_is_wakeup_task_not_wakeup(self, mock_persistence):
        """Test wakeup task detection for non-wakeup task."""
        
        mock_task = MagicMock()
        mock_task.parent_task_id = "OTHER_PARENT"
        mock_task.context = {}
        mock_persistence.get_task_by_id.return_value = mock_task
        
        result = ActionSelectionSpecialCases._is_wakeup_task("test-task")
        
        assert result is False


class TestActionParameterProcessor:
    """Test the parameter processor component."""
    
    def test_process_action_parameters_speak(self):
        """Test processing SPEAK action parameters."""
        
        llm_response = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"content": "Test message"},
            rationale="Test rationale"
        )
        
        triaged_inputs = {}
        
        result = ActionParameterProcessor.process_action_parameters(llm_response, triaged_inputs)
        
        assert result.selected_action == HandlerActionType.SPEAK
        assert isinstance(result.action_parameters, SpeakParams)
        assert result.action_parameters.content == "Test message"
    
    def test_process_action_parameters_ponder(self):
        """Test processing PONDER action parameters."""
        
        llm_response = ActionSelectionResult(
            selected_action=HandlerActionType.PONDER,
            action_parameters={"questions": ["Question 1", "Question 2"]},
            rationale="Need more information"
        )
        
        triaged_inputs = {}
        
        result = ActionParameterProcessor.process_action_parameters(llm_response, triaged_inputs)
        
        assert result.selected_action == HandlerActionType.PONDER
        assert isinstance(result.action_parameters, PonderParams)
        assert len(result.action_parameters.questions) == 2
    
    def test_process_action_parameters_invalid(self):
        """Test processing invalid action parameters."""
        
        llm_response = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"invalid_field": "value"},  # Missing required 'content'
            rationale="Test rationale"
        )
        
        triaged_inputs = {}
        
        result = ActionParameterProcessor.process_action_parameters(llm_response, triaged_inputs)
        
        # Should fall back to dict when validation fails
        assert isinstance(result.action_parameters, dict)
        assert result.action_parameters["invalid_field"] == "value"
    
    def test_inject_channel_id_from_identity_context(self):
        """Test injecting channel ID from identity context."""
        
        mock_context = MagicMock()
        mock_context.identity_context = "The channel is test-channel-123 for communication"
        
        triaged_inputs = {"processing_context": mock_context}
        
        channel_id = ActionParameterProcessor._extract_channel_id(triaged_inputs)
        
        assert channel_id == "test-channel-123"
    
    def test_inject_channel_id_from_task_context(self):
        """Test injecting channel ID from task context."""
        
        mock_context = MagicMock()
        mock_context.identity_context = None
        mock_context.initial_task_context = {"channel_id": "task-channel-456"}
        
        triaged_inputs = {"processing_context": mock_context}
        
        channel_id = ActionParameterProcessor._extract_channel_id(triaged_inputs)
        
        assert channel_id == "task-channel-456"
    
    def test_inject_channel_id_from_system_snapshot(self):
        """Test injecting channel ID from system snapshot."""
        
        mock_context = MagicMock()
        mock_context.identity_context = None
        mock_context.initial_task_context = None
        mock_context.system_snapshot.channel_id = "snapshot-channel-789"
        
        triaged_inputs = {"processing_context": mock_context}
        
        channel_id = ActionParameterProcessor._extract_channel_id(triaged_inputs)
        
        assert channel_id == "snapshot-channel-789"
    
    def test_inject_channel_id_not_found(self):
        """Test channel ID injection when not found."""
        
        mock_context = MagicMock()
        mock_context.identity_context = None
        mock_context.initial_task_context = None
        mock_context.system_snapshot.channel_id = None
        
        triaged_inputs = {"processing_context": mock_context}
        
        channel_id = ActionParameterProcessor._extract_channel_id(triaged_inputs)
        
        assert channel_id is None


class TestFacultyIntegration:
    """Test the faculty integration component."""
    
    @pytest.fixture
    def mock_faculties(self):
        return {
            "entropy": MockFaculty(),
            "coherence": MockFaculty()
        }
    
    @pytest.fixture
    def faculty_integration(self, mock_faculties):
        return FacultyIntegration(mock_faculties)
    
    @pytest.fixture
    def mock_thought(self):
        return Thought(
            thought_id="faculty-test",
            content="Content for faculty analysis",
            source_task_id="test-task-faculty",
            thought_type=ThoughtType.STANDARD,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
    
    @pytest.mark.asyncio
    async def test_apply_faculties_to_content(self, faculty_integration):
        """Test applying faculties to content."""
        
        results = await faculty_integration.apply_faculties_to_content(
            "Test content for analysis",
            {"context": "test"}
        )
        
        assert "entropy" in results
        assert "coherence" in results
        assert results["entropy"].score == 0.8
        assert "Analysis of: Test content for" in results["entropy"].insight
    
    def test_build_faculty_insights_string(self, faculty_integration):
        """Test building faculty insights string."""
        
        faculty_results = {
            "entropy": MockFaculty.__new__(MockFaculty),
            "coherence": MockFaculty.__new__(MockFaculty)
        }
        
        # Manually set attributes since we're not calling __init__
        faculty_results["entropy"].score = 0.6
        faculty_results["coherence"].score = 0.9
        
        insights_str = faculty_integration.build_faculty_insights_string(faculty_results)
        
        assert "EPISTEMIC FACULTY INSIGHTS" in insights_str
        assert "entropy:" in insights_str
        assert "coherence:" in insights_str
        assert "Consider these faculty evaluations" in insights_str
    
    def test_build_faculty_insights_string_empty(self, faculty_integration):
        """Test building insights string with no faculty results."""
        
        insights_str = faculty_integration.build_faculty_insights_string({})
        
        assert insights_str == ""
    
    @pytest.mark.asyncio
    async def test_enhance_evaluation_with_faculties(self, faculty_integration, mock_thought):
        """Test enhancing evaluation with faculty insights."""
        
        triaged_inputs = {
            "original_thought": mock_thought,
            "other_data": "test"
        }
        
        enhanced_inputs = await faculty_integration.enhance_evaluation_with_faculties(
            mock_thought,
            triaged_inputs,
            {"failure_reason": "guardrail_violation"}
        )
        
        assert "faculty_evaluations" in enhanced_inputs
        assert "faculty_enhanced" in enhanced_inputs
        assert "guardrail_context" in enhanced_inputs
        assert enhanced_inputs["faculty_enhanced"] is True
        assert enhanced_inputs["other_data"] == "test"  # Original data preserved
    
    def test_add_faculty_metadata_to_result(self, faculty_integration):
        """Test adding faculty metadata to results."""
        
        original_result = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Original response"),
            rationale="Original rationale"
        )
        
        enhanced_result = faculty_integration.add_faculty_metadata_to_result(
            original_result,
            faculty_enhanced=True,
            recursive_evaluation=True
        )
        
        assert enhanced_result.selected_action == original_result.selected_action
        assert enhanced_result.action_parameters == original_result.action_parameters
        assert "epistemic faculties" in enhanced_result.rationale
        assert "recursive evaluation" in enhanced_result.rationale
        assert "guardrail failure" in enhanced_result.rationale
    
    def test_add_faculty_metadata_no_enhancement(self, faculty_integration):
        """Test metadata addition when no enhancement occurred."""
        
        original_result = ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters=SpeakParams(content="Original response"),
            rationale="Original rationale"
        )
        
        result = faculty_integration.add_faculty_metadata_to_result(
            original_result,
            faculty_enhanced=False
        )
        
        # Should return unchanged result
        assert result == original_result
        assert result.rationale == "Original rationale"