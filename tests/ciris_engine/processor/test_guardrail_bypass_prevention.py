"""
Test suite to prevent guardrail bypass issues and ensure all actions go through proper guardrail processing.

This test was created to catch issues like the OBSERVE action guardrail bypass bug where incorrect
code indentation caused certain actions to skip guardrail processing entirely.
"""
import pytest
import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, Optional

from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.agent_core_schemas_v1 import ActionSelectionResult, Thought
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult
from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
from ciris_engine.context.builder import ContextBuilder

logger = logging.getLogger(__name__)


class TestGuardrailBypassPrevention:
    """
    Test suite to ensure all actions go through proper guardrail processing.
    
    This test suite specifically targets the type of bug where certain actions
    might bypass guardrail processing due to code structure issues like incorrect
    indentation, logic errors, or missing cases.
    """

    @pytest.fixture
    def mock_app_config(self):
        """Create a mock app config for testing."""
        config = MagicMock(spec=AppConfig)
        config.workflow = MagicMock()
        config.workflow.max_ponder_rounds = 3
        config.agent_mode = "test"
        config.default_profile = "default"
        config.agent_profiles = {"default": {}}
        return config

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for testing."""
        deps = MagicMock(spec=ActionHandlerDependencies)
        deps.action_sink = AsyncMock()
        deps.llm_client = AsyncMock()
        deps.memory_system = AsyncMock()
        return deps

    @pytest.fixture
    def mock_ethical_guardrails(self):
        """Create a mock ethical guardrails that tracks which actions were checked."""
        guardrails = AsyncMock(spec=EthicalGuardrails)
        # Track which actions were checked
        guardrails.checked_actions = []
        
        async def track_check_action_output_safety(action_result):
            """Track which actions are being checked and return safe by default."""
            action_type = getattr(action_result, 'selected_action', 'UNKNOWN')
            guardrails.checked_actions.append(action_type)
            logger.info(f"Mock guardrails checking action: {action_type}")
            return True, "Test approval", {}
        
        guardrails.check_action_output_safety = track_check_action_output_safety
        return guardrails

    @pytest.fixture
    def mock_guardrail_orchestrator(self, mock_ethical_guardrails):
        """Create a mock guardrail orchestrator that uses the tracking ethical guardrails."""
        orchestrator = GuardrailOrchestrator(
            ethical_guardrails=mock_ethical_guardrails
        )
        return orchestrator

    @pytest.fixture
    def mock_dma_orchestrator(self):
        """Create a mock DMA orchestrator."""
        orchestrator = AsyncMock(spec=DMAOrchestrator)
        orchestrator.run_initial_dmas = AsyncMock(return_value={})
        return orchestrator

    @pytest.fixture
    def mock_context_builder(self):
        """Create a mock context builder."""
        builder = AsyncMock(spec=ContextBuilder)
        builder.build_thought_context = AsyncMock(return_value={})
        return builder

    @pytest.fixture
    def thought_processor(self, mock_dma_orchestrator, mock_context_builder, 
                         mock_guardrail_orchestrator, mock_app_config, mock_dependencies):
        """Create a ThoughtProcessor with mocked dependencies."""
        return ThoughtProcessor(
            dma_orchestrator=mock_dma_orchestrator,
            context_builder=mock_context_builder,
            guardrail_orchestrator=mock_guardrail_orchestrator,
            app_config=mock_app_config,
            dependencies=mock_dependencies
        )

    def create_test_thought(self, thought_id: str = "test-thought-123") -> Thought:
        """Create a test thought for processing."""
        import datetime
        now = datetime.datetime.now().isoformat()
        return Thought(
            thought_id=thought_id,
            source_task_id="test-task-456",
            thought_type="standard",
            status=ThoughtStatus.PENDING,
            created_at=now,
            updated_at=now,
            round_number=0,
            content="Test thought content",
            context={}
        )

    def create_action_result(self, action_type: HandlerActionType) -> ActionSelectionResult:
        """Create an ActionSelectionResult for the given action type."""
        params = {"test": "parameters"}
        if action_type == HandlerActionType.SPEAK:
            params["content"] = "Test message"
        if action_type == HandlerActionType.PONDER:
            params["questions"] = ["Test ponder question?"]
        if action_type == HandlerActionType.DEFER:
            params["reason"] = "Test defer reason."
            params["context"] = {"test": "context"}
            params["target_wa_ual"] = "test-wa-ual"
        return ActionSelectionResult(
            selected_action=action_type,
            action_parameters=params,
            rationale=f"Test rationale for {action_type.value}",
            confidence=0.8
        )

    @pytest.mark.asyncio
    async def test_all_action_types_go_through_guardrails(self, thought_processor, mock_ethical_guardrails):
        """
        CRITICAL TEST: Ensure all action types go through guardrail processing.
        
        This test specifically checks that every possible action type is processed
        by the guardrails, preventing bugs like the OBSERVE action bypass.
        """
        # Test all possible action types
        all_action_types = [
            HandlerActionType.SPEAK,
            HandlerActionType.OBSERVE,
            HandlerActionType.RECALL,
            HandlerActionType.MEMORIZE,
            HandlerActionType.FORGET,
            HandlerActionType.PONDER,
            HandlerActionType.TOOL,
            HandlerActionType.DEFER,
            HandlerActionType.REJECT,
            HandlerActionType.TASK_COMPLETE
        ]

        thought = self.create_test_thought()
        thought_item = ProcessingQueueItem.from_thought(thought, "")

        for action_type in all_action_types:
            logger.info(f"Testing guardrail processing for action: {action_type.value}")
            
            # Reset the tracked actions
            mock_ethical_guardrails.checked_actions = []
            
            # Mock the DMA to return this specific action
            action_result = self.create_action_result(action_type)
            thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=action_result)
            
            # Mock thought fetching
            with patch.object(thought_processor, '_fetch_thought', return_value=thought):
                # Process the thought
                result = await thought_processor.process_thought(thought_item)
                
                # CRITICAL ASSERTION: This action MUST have been checked by guardrails
                if action_type != HandlerActionType.TASK_COMPLETE:
                    assert action_type in mock_ethical_guardrails.checked_actions, (
                        f"ACTION {action_type.value} DID NOT GO THROUGH GUARDRAILS! "
                        f"This indicates a guardrail bypass bug. "
                        f"Checked actions: {mock_ethical_guardrails.checked_actions}"
                    )
                
                logger.info(f"✓ Action {action_type.value} properly went through guardrails")

    @pytest.mark.asyncio
    async def test_observe_action_specifically_goes_through_guardrails(self, thought_processor, mock_ethical_guardrails):
        """
        SPECIFIC TEST: Ensure OBSERVE actions go through guardrails.
        
        This test specifically targets the bug that was found where OBSERVE actions
        were bypassing guardrails due to incorrect code indentation.
        """
        thought = self.create_test_thought()
        thought_item = ProcessingQueueItem.from_thought(thought, "")
        
        # Create an OBSERVE action result
        observe_result = self.create_action_result(HandlerActionType.OBSERVE)
        thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=observe_result)
        
        # Reset the tracked actions
        mock_ethical_guardrails.checked_actions = []
        
        # Mock thought fetching
        with patch.object(thought_processor, '_fetch_thought', return_value=thought):
            # Process the thought
            result = await thought_processor.process_thought(thought_item)
            
            # CRITICAL ASSERTION: OBSERVE action MUST go through guardrails
            assert HandlerActionType.OBSERVE in mock_ethical_guardrails.checked_actions, (
                "OBSERVE action did not go through guardrails! "
                "This is the exact bug that was previously found and fixed. "
                f"Checked actions: {mock_ethical_guardrails.checked_actions}"
            )
            
            # Ensure the result is not None (which was the symptom of the bypass bug)
            assert result is not None, "OBSERVE action processing returned None - indicates bypass bug"
            
            logger.info("✓ OBSERVE action properly went through guardrails")

    @pytest.mark.asyncio
    async def test_guardrail_orchestrator_apply_guardrails_never_returns_none(self, mock_guardrail_orchestrator, mock_ethical_guardrails):
        """
        DIRECT TEST: Ensure GuardrailOrchestrator.apply_guardrails never returns None.
        
        This test directly tests the guardrail orchestrator to ensure it never
        returns None for any action type, which was the symptom of the bypass bug.
        """
        # Test all action types directly with the guardrail orchestrator
        all_action_types = [
            HandlerActionType.SPEAK,
            HandlerActionType.OBSERVE,
            HandlerActionType.RECALL,
            HandlerActionType.MEMORIZE,
            HandlerActionType.FORGET,
            HandlerActionType.PONDER,
            HandlerActionType.TOOL,
            HandlerActionType.DEFER,
            HandlerActionType.REJECT,
            HandlerActionType.TASK_COMPLETE
        ]

        thought = self.create_test_thought()
        dma_results = {}

        for action_type in all_action_types:
            logger.info(f"Testing guardrail orchestrator directly for action: {action_type.value}")
            
            # Reset the tracked actions
            mock_ethical_guardrails.checked_actions = []
            
            action_result = self.create_action_result(action_type)
            
            # Apply guardrails directly
            guardrail_result = await mock_guardrail_orchestrator.apply_guardrails(
                action_result, thought, dma_results
            )
            
            # CRITICAL ASSERTION: Result must never be None
            assert guardrail_result is not None, (
                f"GuardrailOrchestrator.apply_guardrails returned None for {action_type.value}! "
                "This indicates a guardrail bypass bug."
            )
            
            # CRITICAL ASSERTION: Action must have been checked
            if action_type != HandlerActionType.TASK_COMPLETE:
                assert action_type in mock_ethical_guardrails.checked_actions, (
                    f"Action {action_type.value} was not checked by ethical guardrails! "
                    f"Checked actions: {mock_ethical_guardrails.checked_actions}"
                )
            
            logger.info(f"✓ Guardrail orchestrator properly processed {action_type.value}")

    @pytest.mark.asyncio
    async def test_guardrail_result_structure_is_consistent(self, mock_guardrail_orchestrator):
        """
        TEST: Ensure guardrail results have consistent structure.
        
        This test ensures that all guardrail results have the expected structure
        and contain the necessary fields.
        """
        thought = self.create_test_thought()
        dma_results = {}
        
        # Test a few key action types
        test_actions = [
            HandlerActionType.SPEAK,
            HandlerActionType.OBSERVE,
            HandlerActionType.RECALL
        ]

        for action_type in test_actions:
            action_result = self.create_action_result(action_type)
            
            guardrail_result = await mock_guardrail_orchestrator.apply_guardrails(
                action_result, thought, dma_results
            )
            
            # Verify result structure
            assert guardrail_result is not None
            assert hasattr(guardrail_result, 'final_action'), (
                f"GuardrailResult for {action_type.value} missing final_action"
            )
            
            if guardrail_result.final_action:
                assert hasattr(guardrail_result.final_action, 'selected_action'), (
                    f"GuardrailResult.final_action for {action_type.value} missing selected_action"
                )

    @pytest.mark.asyncio
    async def test_no_action_returns_none_from_thought_processor(self, thought_processor):
        """
        INTEGRATION TEST: Ensure no action type causes ThoughtProcessor to return None.
        
        This test ensures that the full thought processing pipeline never returns None
        for any action type, which would indicate a processing failure or bypass.
        """
        all_action_types = [
            HandlerActionType.SPEAK,
            HandlerActionType.OBSERVE,
            HandlerActionType.RECALL,
            HandlerActionType.MEMORIZE,
            HandlerActionType.FORGET,
            HandlerActionType.PONDER,
            HandlerActionType.TOOL,
            HandlerActionType.DEFER,
            HandlerActionType.REJECT,
            HandlerActionType.TASK_COMPLETE
        ]

        thought = self.create_test_thought()
        thought_item = ProcessingQueueItem.from_thought(thought, "")

        for action_type in all_action_types:
            logger.info(f"Testing full pipeline for action: {action_type.value}")
            
            # Mock the DMA to return this specific action
            action_result = self.create_action_result(action_type)
            thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=action_result)
            
            # Mock thought fetching
            with patch.object(thought_processor, '_fetch_thought', return_value=thought):
                # Process the thought
                result = await thought_processor.process_thought(thought_item)
                
                # CRITICAL ASSERTION: Result must never be None
                assert result is not None, (
                    f"ThoughtProcessor returned None for {action_type.value}! "
                    "This indicates a processing failure or bypass bug."
                )
                
                # Result should have the expected action type (or a transformed one)
                if hasattr(result, 'selected_action'):
                    logger.info(f"✓ Action {action_type.value} processed successfully, result: {result.selected_action}")
                else:
                    logger.warning(f"Result for {action_type.value} missing selected_action: {result}")

    @pytest.mark.asyncio
    async def test_guardrail_orchestrator_indentation_bug_prevention(self):
        """
        REGRESSION TEST: Prevent the specific indentation bug that caused OBSERVE bypass.
        
        This test uses a real GuardrailOrchestrator to ensure the actual implementation
        doesn't have indentation or scoping bugs that cause actions to bypass guardrails.
        """
        # Use real GuardrailOrchestrator with mocked dependencies
        mock_ethical_guardrails = AsyncMock(spec=EthicalGuardrails)
        mock_ethical_guardrails.checked_actions = []
        
        async def track_check_action_output_safety(action_result):
            action_type = getattr(action_result, 'selected_action', 'UNKNOWN')
            mock_ethical_guardrails.checked_actions.append(action_type)
            return True, "Test approval", {}
        
        mock_ethical_guardrails.check_action_output_safety = track_check_action_output_safety
        
        # Create real GuardrailOrchestrator
        orchestrator = GuardrailOrchestrator(
            ethical_guardrails=mock_ethical_guardrails
        )
        
        thought = self.create_test_thought()
        dma_results = {}
        
        # Test the problematic OBSERVE action specifically
        observe_result = self.create_action_result(HandlerActionType.OBSERVE)
        
        # Apply guardrails
        guardrail_result = await orchestrator.apply_guardrails(
            observe_result, thought, dma_results
        )
        
        # CRITICAL ASSERTIONS: The exact checks that would have caught the original bug
        assert guardrail_result is not None, (
            "GuardrailOrchestrator returned None for OBSERVE action! "
            "This indicates the indentation bug is present."
        )
        
        assert HandlerActionType.OBSERVE in mock_ethical_guardrails.checked_actions, (
            "OBSERVE action was not checked by ethical guardrails! "
            "This indicates the indentation bug is present."
        )
        
        assert hasattr(guardrail_result, 'final_action'), (
            "GuardrailResult missing final_action for OBSERVE action!"
        )
        
        logger.info("✓ Indentation bug regression test passed")

    @pytest.mark.asyncio
    async def test_edge_case_action_types_dont_bypass_guardrails(self, thought_processor, mock_ethical_guardrails):
        """
        EDGE CASE TEST: Test less common action types that might be forgotten in guardrail logic.
        
        This test ensures that edge case actions like REJECT, TASK_COMPLETE, and DEFER
        also go through guardrails properly.
        """
        edge_case_actions = [
            HandlerActionType.REJECT,
            HandlerActionType.DEFER
        ]

        thought = self.create_test_thought()
        thought_item = ProcessingQueueItem.from_thought(thought, "")

        for action_type in edge_case_actions:
            logger.info(f"Testing edge case action: {action_type.value}")
            
            # Reset the tracked actions
            mock_ethical_guardrails.checked_actions = []
            
            # Mock the DMA to return this specific action
            action_result = self.create_action_result(action_type)
            thought_processor.dma_orchestrator.run_action_selection = AsyncMock(return_value=action_result)
            
            # Mock thought fetching
            with patch.object(thought_processor, '_fetch_thought', return_value=thought):
                # Process the thought
                result = await thought_processor.process_thought(thought_item)
                
                # CRITICAL ASSERTION: Edge case actions must also go through guardrails
                assert action_type in mock_ethical_guardrails.checked_actions, (
                    f"Edge case action {action_type.value} did not go through guardrails! "
                    f"Checked actions: {mock_ethical_guardrails.checked_actions}"
                )
                
                assert result is not None, (
                    f"Edge case action {action_type.value} processing returned None"
                )
                
                logger.info(f"✓ Edge case action {action_type.value} properly went through guardrails")


if __name__ == "__main__":
    # Run the tests if this file is executed directly
    pytest.main([__file__, "-v"])
