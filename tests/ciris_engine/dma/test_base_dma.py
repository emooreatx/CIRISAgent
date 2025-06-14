"""Tests for the base DMA class and prompt loading functionality."""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
from typing import Dict, Any, Optional

from ciris_engine.dma.base_dma import BaseDMA
from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.protocols.faculties import EpistemicFaculty
from pydantic import BaseModel


class MockFaculty:
    """Mock epistemic faculty for testing."""
    
    async def evaluate(self, content: str, context: Optional[Dict[str, Any]] = None) -> BaseModel:
        class MockResult(BaseModel):
            score: float = 0.7
            analysis: str = "Mock analysis"
        return MockResult()


class TestBaseDMA(BaseDMA):
    """Concrete implementation of BaseDMA for testing."""
    
    # Test default prompts
    DEFAULT_PROMPT = {
        "system_header": "Test system header",
        "evaluation_template": "Evaluate: {content}",
        "decision_criteria": "Use test criteria"
    }
    
    DEFAULT_PROMPT_TEMPLATE = {
        "template_header": "Template header",
        "template_body": "Template body"
    }
    
    async def evaluate(self, *args, **kwargs) -> BaseModel:
        """Mock evaluate method."""
        class MockResult(BaseModel):
            result: str = "test_result"
        return MockResult()


class TestBaseDMAInitialization:
    """Test BaseDMA initialization and setup."""
    
    @pytest.fixture
    def mock_service_registry(self):
        registry = MagicMock(spec=ServiceRegistry)
        mock_service = MagicMock()
        registry.get_service.return_value = mock_service
        return registry
    
    @pytest.fixture
    def mock_faculties(self):
        return {"test_faculty": MockFaculty()}
    
    def test_basic_initialization(self, mock_service_registry):
        """Test basic DMA initialization."""
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        assert dma.service_registry == mock_service_registry
        assert dma.model_name is None
        assert dma.max_retries == 3
        assert dma.faculties == {}
        assert isinstance(dma.prompts, dict)
    
    def test_initialization_with_parameters(self, mock_service_registry, mock_faculties):
        """Test DMA initialization with all parameters."""
        
        prompt_overrides = {"custom_prompt": "Custom value"}
        
        dma = TestBaseDMA(
            service_registry=mock_service_registry,
            model_name="test-model",
            max_retries=5,
            prompt_overrides=prompt_overrides,
            faculties=mock_faculties,
            custom_param="custom_value"
        )
        
        assert dma.model_name == "test-model"
        assert dma.max_retries == 5
        assert dma.faculties == mock_faculties
        assert "custom_prompt" in dma.prompts
        assert dma.prompts["custom_prompt"] == "Custom value"
    
    
    @pytest.mark.asyncio
    async def test_get_llm_service(self, mock_service_registry):
        """Test LLM service retrieval."""
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        service = await dma.get_llm_service()
        
        mock_service_registry.get_service.assert_called_once_with(
            handler="TestBaseDMA",
            service_type="llm"
        )
        assert service is not None


class TestPromptLoading:
    """Test prompt loading functionality."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    def test_load_prompts_from_default_prompt(self, mock_service_registry):
        """Test loading prompts from DEFAULT_PROMPT class attribute."""
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        # Should load from DEFAULT_PROMPT
        assert "system_header" in dma.prompts
        assert dma.prompts["system_header"] == "Test system header"
        assert "evaluation_template" in dma.prompts
    
    def test_load_prompts_with_overrides(self, mock_service_registry):
        """Test loading prompts with overrides."""
        
        overrides = {
            "system_header": "Overridden header",
            "new_prompt": "New prompt value"
        }
        
        dma = TestBaseDMA(
            service_registry=mock_service_registry,
            prompt_overrides=overrides
        )
        
        # Should have overridden value
        assert dma.prompts["system_header"] == "Overridden header"
        # Should have new prompt
        assert dma.prompts["new_prompt"] == "New prompt value"
        # Should keep non-overridden defaults
        assert dma.prompts["evaluation_template"] == "Evaluate: {content}"
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_prompts_from_yaml_file(self, mock_yaml_load, mock_file, mock_exists, mock_service_registry):
        """Test loading prompts from YAML file."""
        
        # Mock YAML file content
        yaml_content = {
            "system_header": "YAML system header",
            "yaml_specific": "YAML value",
            "evaluation_template": "YAML evaluation template"
        }
        
        mock_exists.return_value = True
        mock_yaml_load.return_value = yaml_content
        
        # Mock the module path to make YAML file findable
        with patch.object(TestBaseDMA, '__module__', 'ciris_engine.dma.test_dma'):
            dma = TestBaseDMA(service_registry=mock_service_registry)
        
        # Should load from YAML
        assert dma.prompts["system_header"] == "YAML system header"
        assert dma.prompts["yaml_specific"] == "YAML value"
        assert dma.prompts["evaluation_template"] == "YAML evaluation template"
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load')
    def test_load_prompts_yaml_file_with_overrides(self, mock_yaml_load, mock_file, mock_exists, mock_service_registry):
        """Test loading prompts from YAML file with overrides."""
        
        yaml_content = {
            "system_header": "YAML header",
            "yaml_prompt": "YAML value"
        }
        
        overrides = {
            "system_header": "Override header",
            "override_prompt": "Override value"
        }
        
        mock_exists.return_value = True
        mock_yaml_load.return_value = yaml_content
        
        with patch.object(TestBaseDMA, '__module__', 'ciris_engine.dma.test_dma'):
            dma = TestBaseDMA(
                service_registry=mock_service_registry,
                prompt_overrides=overrides
            )
        
        # Override should take precedence
        assert dma.prompts["system_header"] == "Override header"
        # YAML value should be preserved
        assert dma.prompts["yaml_prompt"] == "YAML value"
        # Override-only value should be included
        assert dma.prompts["override_prompt"] == "Override value"
    
    @patch('pathlib.Path.exists')
    def test_load_prompts_yaml_file_not_exists(self, mock_exists, mock_service_registry):
        """Test loading prompts when YAML file doesn't exist."""
        
        mock_exists.return_value = False
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        # Should fall back to DEFAULT_PROMPT
        assert "system_header" in dma.prompts
        assert dma.prompts["system_header"] == "Test system header"
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', side_effect=IOError("File read error"))
    def test_load_prompts_yaml_file_read_error(self, mock_file, mock_exists, mock_service_registry):
        """Test handling of YAML file read errors."""
        
        mock_exists.return_value = True
        
        # Should handle error gracefully and fall back to defaults
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        # Should fall back to DEFAULT_PROMPT
        assert "system_header" in dma.prompts
        assert dma.prompts["system_header"] == "Test system header"
    
    @patch('pathlib.Path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.safe_load', side_effect=yaml.YAMLError("Invalid YAML"))
    def test_load_prompts_yaml_parse_error(self, mock_yaml_load, mock_file, mock_exists, mock_service_registry):
        """Test handling of YAML parse errors."""
        
        mock_exists.return_value = True
        
        # Should handle YAML parse error gracefully
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        # Should fall back to DEFAULT_PROMPT
        assert "system_header" in dma.prompts
        assert dma.prompts["system_header"] == "Test system header"


class TestDMAWithoutDefaults:
    """Test DMA behavior when no default prompts are defined."""
    
    class MinimalDMA(BaseDMA):
        """DMA without default prompts."""
        
        async def evaluate(self, *args, **kwargs) -> BaseModel:
            class MockResult(BaseModel):
                result: str = "minimal_result"
            return MockResult()
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    def test_minimal_dma_initialization(self, mock_service_registry):
        """Test DMA initialization without default prompts."""
        
        dma = self.MinimalDMA(service_registry=mock_service_registry)
        
        # Should have empty prompts dict
        assert dma.prompts == {}
    
    def test_minimal_dma_with_overrides(self, mock_service_registry):
        """Test minimal DMA with prompt overrides."""
        
        overrides = {"custom_prompt": "Custom value"}
        
        dma = self.MinimalDMA(
            service_registry=mock_service_registry,
            prompt_overrides=overrides
        )
        
        # Should only have override prompts
        assert dma.prompts == overrides


class TestDMAWithDefaultTemplate:
    """Test DMA behavior with DEFAULT_PROMPT_TEMPLATE instead of DEFAULT_PROMPT."""
    
    class TemplateDMA(BaseDMA):
        """DMA with DEFAULT_PROMPT_TEMPLATE."""
        
        DEFAULT_PROMPT_TEMPLATE = {
            "template_header": "Template system header",
            "template_guidance": "Template guidance"
        }
        
        async def evaluate(self, *args, **kwargs) -> BaseModel:
            class MockResult(BaseModel):
                result: str = "template_result"
            return MockResult()
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    def test_template_dma_initialization(self, mock_service_registry):
        """Test DMA with DEFAULT_PROMPT_TEMPLATE."""
        
        dma = self.TemplateDMA(service_registry=mock_service_registry)
        
        # Should load from DEFAULT_PROMPT_TEMPLATE
        assert "template_header" in dma.prompts
        assert dma.prompts["template_header"] == "Template system header"
        assert "template_guidance" in dma.prompts


class TestDMAFacultyIntegration:
    """Test DMA faculty integration functionality."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.fixture
    def mock_faculties(self):
        return {
            "faculty1": MockFaculty(),
            "faculty2": MockFaculty()
        }
    
    @pytest.mark.asyncio
    async def test_apply_faculties_success(self, mock_service_registry, mock_faculties):
        """Test successful faculty application."""
        
        dma = TestBaseDMA(
            service_registry=mock_service_registry,
            faculties=mock_faculties
        )
        
        results = await dma.apply_faculties("test content", {"context": "test"})
        
        assert "faculty1" in results
        assert "faculty2" in results
        assert results["faculty1"].score == 0.7
        assert results["faculty2"].analysis == "Mock analysis"
    
    @pytest.mark.asyncio
    async def test_apply_faculties_no_faculties(self, mock_service_registry):
        """Test faculty application when no faculties are available."""
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        results = await dma.apply_faculties("test content")
        
        assert results == {}
    
    @pytest.mark.asyncio
    async def test_apply_faculties_with_error(self, mock_service_registry):
        """Test faculty application when one faculty raises an error."""
        
        class FailingFaculty:
            async def evaluate(self, content, context=None):
                raise Exception("Faculty evaluation failed")
        
        faculties = {
            "working_faculty": MockFaculty(),
            "failing_faculty": FailingFaculty()
        }
        
        dma = TestBaseDMA(
            service_registry=mock_service_registry,
            faculties=faculties
        )
        
        # Should not raise exception, should handle error gracefully
        results = await dma.apply_faculties("test content")
        
        # Should have result from working faculty
        assert "working_faculty" in results
        # Should not have result from failing faculty
        assert "failing_faculty" not in results


class TestDMAEvaluateMethod:
    """Test the abstract evaluate method."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    @pytest.mark.asyncio
    async def test_evaluate_method_called(self, mock_service_registry):
        """Test that evaluate method can be called."""
        
        dma = TestBaseDMA(service_registry=mock_service_registry)
        
        result = await dma.evaluate("test_input", param="value")
        
        assert result is not None
        assert result.result == "test_result"
    
    def test_abstract_evaluate_method(self, mock_service_registry):
        """Test that BaseDMA enforce implementation of evaluate method."""
        
        # This test ensures that BaseDMA is properly abstract
        class IncompleteDMA(BaseDMA):
            pass  # Missing evaluate method
        
        # Should NOT be able to instantiate abstract class without implementing evaluate
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteDMA(service_registry=mock_service_registry)


class TestDMARepr:
    """Test DMA string representation."""
    
    @pytest.fixture
    def mock_service_registry(self):
        return MagicMock(spec=ServiceRegistry)
    
    def test_dma_repr(self, mock_service_registry):
        """Test that DMA has a useful string representation."""
        
        dma = TestBaseDMA(
            service_registry=mock_service_registry,
            model_name="test-model"
        )
        
        # Should not crash when converted to string
        str_repr = str(dma)
        assert str_repr is not None
        assert len(str_repr) > 0