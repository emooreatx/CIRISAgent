"""
Unit tests for improved validation error formatting.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field, ValidationError

from ciris_engine.logic.infrastructure.handlers.base_handler import BaseActionHandler
from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.enums import HandlerScope


class TestValidationErrorFormatting:
    """Test suite for validation error message formatting."""

    class SampleParams(BaseModel):
        """Sample parameter model for testing."""

        required_field: str
        optional_field: str = "default"
        number_field: int = Field(ge=0, le=100)

    class TestHandler(BaseActionHandler):
        """Test handler for validation testing."""

        def __init__(self):
            # Mock the required attributes
            self.handler_name = "TestHandler"
            self.scope = HandlerScope.RUNTIME
            self.priority = 5
            self._time_service = MagicMock()
            self._started = True

        async def handle(self, result: ActionSelectionDMAResult) -> ActionSelectionDMAResult:
            """Mock handle method."""
            return result

    def test_validation_error_simple(self):
        """Test formatting of simple validation errors."""
        handler = self.TestHandler()

        # Missing required field
        params = {"optional_field": "test"}

        with pytest.raises(ValueError) as exc_info:
            handler._validate_params(params, self.SampleParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for SampleParams" in error_msg
        assert "required_field: Field required" in error_msg
        # Should NOT contain Pydantic URLs
        assert "pydantic.dev" not in error_msg
        assert "For further information" not in error_msg

    def test_validation_error_multiple(self):
        """Test formatting of multiple validation errors."""
        handler = self.TestHandler()

        # Multiple errors
        params = {
            "number_field": 150,  # Out of range
            "optional_field": 123,  # Wrong type
            # Missing required_field
        }

        with pytest.raises(ValueError) as exc_info:
            handler._validate_params(params, self.SampleParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for SampleParams" in error_msg
        # Should show first 3 errors
        assert "required_field: Field required" in error_msg
        assert "optional_field: Input should be a valid string" in error_msg
        assert "number_field: Input should be less than or equal to 100" in error_msg

    def test_validation_error_many(self):
        """Test formatting when there are more than 3 errors."""

        class ComplexParams(BaseModel):
            field1: str
            field2: str
            field3: str
            field4: str
            field5: str

        handler = self.TestHandler()
        params = {}  # All fields missing

        with pytest.raises(ValueError) as exc_info:
            handler._validate_params(params, ComplexParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for ComplexParams" in error_msg
        # Should show first 3 errors
        assert "field1: Field required" in error_msg
        assert "field2: Field required" in error_msg
        assert "field3: Field required" in error_msg
        # Should indicate there are more
        assert "(and 2 more)" in error_msg
        # Should NOT show all 5 errors
        assert "field5" not in error_msg

    def test_validation_error_nested(self):
        """Test formatting of nested field errors."""

        class NestedModel(BaseModel):
            inner_field: str

        class OuterParams(BaseModel):
            nested: NestedModel
            simple: str

        handler = self.TestHandler()
        params = {"nested": {"inner_field": 123}, "simple": "ok"}  # Wrong type in nested field

        with pytest.raises(ValueError) as exc_info:
            handler._validate_params(params, OuterParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for OuterParams" in error_msg
        assert "nested.inner_field: Input should be a valid string" in error_msg

    def test_validation_error_from_model(self):
        """Test validation when params is already a BaseModel."""
        handler = self.TestHandler()

        # Create an invalid model instance (this shouldn't happen in practice)
        # We'll use model_validate to trigger validation
        with pytest.raises(ValueError) as exc_info:
            invalid_data = MagicMock()
            invalid_data.model_dump.return_value = {"number_field": 200}
            handler._validate_params(invalid_data, self.SampleParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for SampleParams" in error_msg

    def test_valid_params(self):
        """Test that valid params pass through correctly."""
        handler = self.TestHandler()

        params = {"required_field": "test", "optional_field": "optional", "number_field": 50}

        result = handler._validate_params(params, self.SampleParams)
        assert isinstance(result, self.SampleParams)
        assert result.required_field == "test"
        assert result.optional_field == "optional"
        assert result.number_field == 50

    def test_extra_fields(self):
        """Test handling of extra fields in parameters."""
        handler = self.TestHandler()

        params = {"required_field": "test", "extra_field": "should_cause_error"}

        with pytest.raises(ValueError) as exc_info:
            handler._validate_params(params, self.SampleParams)

        error_msg = str(exc_info.value)
        assert "Invalid parameters for SampleParams" in error_msg
        assert "extra_field: Extra inputs are not permitted" in error_msg
