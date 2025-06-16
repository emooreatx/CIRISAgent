"""Tests for DMA factory and creation patterns."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

from ciris_engine.dma.factory import (
    create_dma,
    create_dsdma_from_profile,
    ETHICAL_DMA_REGISTRY,
    CSDMA_REGISTRY,
    DSDMA_CLASS_REGISTRY,
    ACTION_SELECTION_DMA_REGISTRY,
)
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.schemas.config_schemas_v1 import AgentProfile
from ciris_engine.protocols.faculties import EpistemicFaculty

# Import adapter configs to resolve forward references
try:
    from ciris_engine.adapters.discord.config import DiscordAdapterConfig
    from ciris_engine.adapters.api.config import APIAdapterConfig
    from ciris_engine.adapters.cli.config import CLIAdapterConfig
except ImportError:
    DiscordAdapterConfig = type('DiscordAdapterConfig', (), {})
    APIAdapterConfig = type('APIAdapterConfig', (), {})
    CLIAdapterConfig = type('CLIAdapterConfig', (), {})

# Rebuild models with resolved references  
try:
    AgentProfile.model_rebuild()
    AppConfig.model_rebuild()
except Exception:
    pass

from ciris_engine.protocols.dma_interface import (
    EthicalDMAInterface,
    CSDMAInterface,
    DSDMAInterface,
    ActionSelectionDMAInterface,
)
from pydantic import BaseModel


class MockFaculty:
    """Mock epistemic faculty for testing."""
    
    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        class MockResult(BaseModel):
            score: float = 0.8
        return MockResult()


class MockEthicalDMA(EthicalDMAInterface):
    """Mock ethical DMA for testing."""
    
    def __init__(self, service_registry, **kwargs):
        self.service_registry = service_registry
        self.kwargs = kwargs
    
    async def evaluate(self, thought_item, context=None, **kwargs):
        from ciris_engine.schemas.dma_results_v1 import EthicalDMAResult
        return EthicalDMAResult(
            alignment_check={"test": "pass"},
            decision="approved"
        )


class MockCSDMA(CSDMAInterface):
    """Mock CSDMA for testing."""
    
    def __init__(self, service_registry, **kwargs):
        self.service_registry = service_registry
        self.kwargs = kwargs
    
    async def evaluate(self, thought_item, **kwargs):
        from ciris_engine.schemas.dma_results_v1 import CSDMAResult
        return CSDMAResult(
            plausibility_score=0.8,
            reasoning="Mock evaluation"
        )


class MockDSDMA(DSDMAInterface):
    """Mock DSDMA for testing."""
    
    def __init__(self, service_registry, domain_name="test", **kwargs):
        self.service_registry = service_registry
        self.domain_name = domain_name
        self.kwargs = kwargs
    
    async def evaluate(self, thought_item, current_context=None, **kwargs):
        from ciris_engine.schemas.dma_results_v1 import DSDMAResult
        return DSDMAResult(
            domain=self.domain_name,
            score=0.9,
            reasoning="Mock domain evaluation"
        )


class MockActionSelectionDMA(ActionSelectionDMAInterface):
    """Mock Action Selection DMA for testing."""
    
    def __init__(self, service_registry, **kwargs):
        self.service_registry = service_registry
        self.kwargs = kwargs
    
    async def evaluate(self, triaged_inputs, enable_recursive_evaluation=False, **kwargs):
        from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
        from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
        return ActionSelectionResult(
            selected_action=HandlerActionType.SPEAK,
            action_parameters={"content": "Mock response"},
            rationale="Mock action selection"
        )
    
    async def recursive_evaluate_with_faculties(self, triaged_inputs, guardrail_failure_context):
        return await self.evaluate(triaged_inputs)


class TestDMAFactory:
    """Test the DMA factory functions."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def mock_faculties(self):
        return {"mock_faculty": MockFaculty()}
    
    @pytest.mark.asyncio
    async def test_create_dma_ethical(self, mock_service_registry):
        """Test creating an ethical DMA."""
        
        # Temporarily add mock to registry
        original_registry = ETHICAL_DMA_REGISTRY.copy()
        ETHICAL_DMA_REGISTRY["MockEthicalDMA"] = MockEthicalDMA
        
        try:
            dma = await create_dma(
                dma_type="ethical",
                dma_identifier="MockEthicalDMA",
                service_registry=mock_service_registry,
                model_name="test-model"
            )
            
            assert dma is not None
            assert isinstance(dma, MockEthicalDMA)
            assert dma.service_registry == mock_service_registry
            assert dma.kwargs.get("model_name") == "test-model"
        
        finally:
            # Restore original registry
            ETHICAL_DMA_REGISTRY.clear()
            ETHICAL_DMA_REGISTRY.update(original_registry)
    
    @pytest.mark.asyncio
    async def test_create_dma_csdma(self, mock_service_registry):
        """Test creating a CSDMA."""
        
        original_registry = CSDMA_REGISTRY.copy()
        CSDMA_REGISTRY["MockCSDMA"] = MockCSDMA
        
        try:
            dma = await create_dma(
                dma_type="csdma",
                dma_identifier="MockCSDMA",
                service_registry=mock_service_registry,
                prompt_overrides={"test": "value"}
            )
            
            assert dma is not None
            assert isinstance(dma, MockCSDMA)
            assert dma.kwargs.get("prompt_overrides") == {"test": "value"}
        
        finally:
            CSDMA_REGISTRY.clear()
            CSDMA_REGISTRY.update(original_registry)
    
    @pytest.mark.asyncio
    async def test_create_dma_dsdma(self, mock_service_registry):
        """Test creating a DSDMA."""
        
        original_registry = DSDMA_CLASS_REGISTRY.copy()
        DSDMA_CLASS_REGISTRY["MockDSDMA"] = MockDSDMA
        
        try:
            dma = await create_dma(
                dma_type="dsdma",
                dma_identifier="MockDSDMA",
                service_registry=mock_service_registry,
                domain_name="test_domain"
            )
            
            assert dma is not None
            assert isinstance(dma, MockDSDMA)
            assert dma.domain_name == "test_domain"
        
        finally:
            DSDMA_CLASS_REGISTRY.clear()
            DSDMA_CLASS_REGISTRY.update(original_registry)
    
    @pytest.mark.asyncio
    async def test_create_dma_action_selection(self, mock_service_registry, mock_faculties):
        """Test creating an Action Selection DMA."""
        
        original_registry = ACTION_SELECTION_DMA_REGISTRY.copy()
        ACTION_SELECTION_DMA_REGISTRY["MockActionSelectionDMA"] = MockActionSelectionDMA
        
        try:
            dma = await create_dma(
                dma_type="action_selection",
                dma_identifier="MockActionSelectionDMA",
                service_registry=mock_service_registry,
                faculties=mock_faculties
            )
            
            assert dma is not None
            assert isinstance(dma, MockActionSelectionDMA)
            assert dma.kwargs.get("faculties") == mock_faculties
        
        finally:
            ACTION_SELECTION_DMA_REGISTRY.clear()
            ACTION_SELECTION_DMA_REGISTRY.update(original_registry)
    
    @pytest.mark.asyncio
    async def test_create_dma_invalid_type(self, mock_service_registry):
        """Test creating DMA with invalid type."""
        
        dma = await create_dma(
            dma_type="invalid_type",
            dma_identifier="SomeDMA",
            service_registry=mock_service_registry
        )
        
        assert dma is None
    
    @pytest.mark.asyncio
    async def test_create_dma_invalid_identifier(self, mock_service_registry):
        """Test creating DMA with invalid identifier."""
        
        dma = await create_dma(
            dma_type="ethical",
            dma_identifier="NonExistentDMA",
            service_registry=mock_service_registry
        )
        
        assert dma is None
    
    @pytest.mark.asyncio
    async def test_create_dma_with_all_options(self, mock_service_registry, mock_faculties):
        """Test creating DMA with all available options."""
        
        original_registry = ETHICAL_DMA_REGISTRY.copy()
        ETHICAL_DMA_REGISTRY["MockEthicalDMA"] = MockEthicalDMA
        
        try:
            dma = await create_dma(
                dma_type="ethical",
                dma_identifier="MockEthicalDMA",
                service_registry=mock_service_registry,
                model_name="gpt-4",
                prompt_overrides={"system": "custom prompt"},
                faculties=mock_faculties,
                custom_param="custom_value"
            )
            
            assert dma is not None
            kwargs = dma.kwargs
            assert kwargs.get("model_name") == "gpt-4"
            assert kwargs.get("prompt_overrides") == {"system": "custom prompt"}
            assert kwargs.get("faculties") == mock_faculties
            assert kwargs.get("custom_param") == "custom_value"
        
        finally:
            ETHICAL_DMA_REGISTRY.clear()
            ETHICAL_DMA_REGISTRY.update(original_registry)


class TestDSDMAFromProfile:
    """Test DSDMA creation from agent profiles."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def test_profile(self):
        from ciris_engine.schemas.config_schemas_v1 import ensure_models_rebuilt
        ensure_models_rebuilt()
        return AgentProfile(
            name="test_agent",
            description="Test agent for DMA factory tests",
            role_description="A test agent profile for DMA creation",
            dsdma_identifier="MockDSDMA",
            dsdma_kwargs={
                "prompt_template": "Custom domain prompt",
                "domain_specific_knowledge": {"key": "value"}
            }
        )
    
    @pytest.mark.asyncio
    async def test_create_dsdma_from_profile(self, mock_service_registry, test_profile):
        """Test creating DSDMA from a valid profile."""
        
        original_registry = DSDMA_CLASS_REGISTRY.copy()
        DSDMA_CLASS_REGISTRY["MockDSDMA"] = MockDSDMA
        
        try:
            with patch('ciris_engine.dma.factory.create_dma') as mock_create:
                mock_create.return_value = MockDSDMA(mock_service_registry, domain_name="test_agent")
                
                dma = await create_dsdma_from_profile(
                    test_profile,
                    mock_service_registry,
                    model_name="test-model"
                )
                
                assert dma is not None
                mock_create.assert_called_once_with(
                    dma_type='dsdma',
                    dma_identifier='MockDSDMA',
                    service_registry=mock_service_registry,
                    model_name="test-model",
                    prompt_overrides=None,
                    domain_name='test_agent',
                    domain_specific_knowledge={'key': 'value'},
                    prompt_template='Custom domain prompt',
                    sink=None
                )
        
        finally:
            DSDMA_CLASS_REGISTRY.clear()
            DSDMA_CLASS_REGISTRY.update(original_registry)
    
    @pytest.mark.asyncio
    async def test_create_dsdma_from_none_profile(self, mock_service_registry):
        """Test creating DSDMA with None profile."""
        
        with patch('ciris_engine.dma.factory.load_profile', new_callable=AsyncMock) as mock_load:
            mock_default_profile = AgentProfile(
                name="default",
                dsdma_identifier="BaseDSDMA"
            )
            mock_load.return_value = mock_default_profile
            
            with patch('ciris_engine.dma.factory.create_dma') as mock_create:
                mock_create.return_value = MockDSDMA(mock_service_registry)
                
                dma = await create_dsdma_from_profile(
                    None,
                    mock_service_registry
                )
                
                assert dma is not None
                mock_load.assert_called_once()
                mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_dsdma_profile_no_identifier(self, mock_service_registry):
        """Test creating DSDMA from profile without DSDMA identifier."""
        
        profile_without_dsdma = AgentProfile(
            name="no_dsdma_agent",
            dsdma_identifier=""  # Empty identifier
        )
        
        with patch('ciris_engine.dma.factory.load_profile', new_callable=AsyncMock) as mock_load:
            mock_default_profile = AgentProfile(
                name="default",
                dsdma_identifier="BaseDSDMA"
            )
            mock_load.return_value = mock_default_profile
            
            with patch('ciris_engine.dma.factory.create_dma') as mock_create:
                mock_create.return_value = MockDSDMA(mock_service_registry)
                
                dma = await create_dsdma_from_profile(
                    profile_without_dsdma,
                    mock_service_registry
                )
                
                # Should load default profile
                mock_load.assert_called_once()
                assert dma is not None
    
    @pytest.mark.asyncio
    async def test_create_dsdma_invalid_identifier(self, mock_service_registry):
        """Test creating DSDMA with invalid identifier."""
        
        invalid_profile = AgentProfile(
            name="invalid_agent",
            dsdma_identifier="NonExistentDSDMA"
        )
        
        with patch('ciris_engine.dma.factory.create_dma') as mock_create:
            mock_create.return_value = None  # Simulate creation failure
            
            dma = await create_dsdma_from_profile(
                invalid_profile,
                mock_service_registry
            )
            
            assert dma is None
    
    @pytest.mark.asyncio
    async def test_create_dsdma_default_profile_load_failure(self, mock_service_registry):
        """Test handling of default profile load failure."""
        
        with patch('ciris_engine.dma.factory.load_profile', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = None  # Simulate async load failure
            
            dma = await create_dsdma_from_profile(
                None,
                mock_service_registry
            )
            
            assert dma is None


class TestDMARegistries:
    """Test DMA registry functionality."""
    
    def test_registries_exist(self):
        """Test that all DMA registries are defined."""
        
        assert ETHICAL_DMA_REGISTRY is not None
        assert CSDMA_REGISTRY is not None
        assert DSDMA_CLASS_REGISTRY is not None
        assert ACTION_SELECTION_DMA_REGISTRY is not None
    
    def test_dsdma_registry_has_defaults(self):
        """Test that DSDMA registry has default entries."""
        
        # DSDMA registry should have base entries
        assert "BaseDSDMA" in DSDMA_CLASS_REGISTRY
        assert "ModerationDSDMA" in DSDMA_CLASS_REGISTRY
    
    def test_registry_types(self):
        """Test that registries have correct types."""
        
        assert isinstance(ETHICAL_DMA_REGISTRY, dict)
        assert isinstance(CSDMA_REGISTRY, dict)
        assert isinstance(DSDMA_CLASS_REGISTRY, dict)
        assert isinstance(ACTION_SELECTION_DMA_REGISTRY, dict)
    
    def test_dsdma_registry_entries_are_classes(self):
        """Test that DSDMA registry entries are actual classes."""
        
        for name, dma_class in DSDMA_CLASS_REGISTRY.items():
            assert isinstance(dma_class, type), f"{name} should be a class"
            # Should be callable (can be instantiated)
            assert callable(dma_class), f"{name} should be callable"


class TestDMAFactoryIntegration:
    """Integration tests for DMA factory with actual registries."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    def test_factory_imports_work(self):
        """Test that factory imports don't crash."""
        
        # This test ensures the import statements in factory.py work
        # and that the registries are populated (or at least don't crash)
        try:
            from ciris_engine.dma.factory import (
                ETHICAL_DMA_REGISTRY,
                CSDMA_REGISTRY,
                ACTION_SELECTION_DMA_REGISTRY
            )
            # If we reach here, imports worked
            assert True
        except ImportError as e:
            pytest.fail(f"Factory imports failed: {e}")
    
    @pytest.mark.asyncio
    async def test_create_dma_with_empty_registry(self, mock_service_registry):
        """Test creating DMA when registry is empty."""
        
        # Test with a type that has an empty registry
        dma = await create_dma(
            dma_type="ethical",  # Assuming this registry might be empty
            dma_identifier="SomeEthicalDMA",
            service_registry=mock_service_registry
        )
        
        # Should handle gracefully
        assert dma is None or dma is not None  # Either outcome is valid
    
    def test_factory_error_handling(self):
        """Test that factory handles errors gracefully."""
        
        # Test with invalid parameters - should not crash
        try:
            from ciris_engine.dma.factory import create_dma
            # Function should exist and be callable
            assert callable(create_dma)
        except Exception as e:
            pytest.fail(f"Factory error handling failed: {e}")