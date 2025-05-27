import pytest
from unittest.mock import AsyncMock, MagicMock, call
import asyncio

# Module to test
from ciris_engine.faculties.epistemic import (
    _create_entropy_messages_for_instructor,
    _create_coherence_messages_for_instructor,
    calculate_epistemic_values,
    DEFAULT_OPENAI_MODEL_NAME
)
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
import instructor # For type hinting the mock

# --- Fixtures ---

@pytest.fixture
def mock_instructor_client():
    """Mocks an instructor-patched AsyncOpenAI client."""
    mock_client = AsyncMock(spec=instructor.Instructor) # Use instructor.Instructor for spec
    # Mock the nested structure instructor uses
    mock_client.chat = AsyncMock()
    mock_client.chat.completions = AsyncMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client

# --- Test Cases ---

def test_create_entropy_messages():
    """Verify the structure of entropy messages."""
    text = "Sample text for entropy."
    messages = _create_entropy_messages_for_instructor(text)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "IRIS-E" in messages[0]["content"]
    assert '{"entropy": <0.00-1.00>}' not in messages[0]["content"] # Ensure coherence prompt isn't mixed in
    assert '{"entropy": 0.07}' in messages[0]["content"] # Check calibration example
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].endswith(text)

def test_create_coherence_messages():
    """Verify the structure of coherence messages."""
    text = "Sample text for coherence."
    messages = _create_coherence_messages_for_instructor(text)
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert "IRIS-C" in messages[0]["content"]
    assert '{"coherence": <0.00-1.00>}' in messages[0]["content"]
    assert '{"entropy": <0.00-1.00>}' not in messages[0]["content"] # Ensure entropy prompt isn't mixed in
    assert "↦ 0.85" in messages[0]["content"] # Check calibration example
    assert messages[1]["role"] == "user"
    assert messages[1]["content"].endswith(text)

@pytest.mark.asyncio
async def test_calculate_epistemic_values_success(mock_instructor_client):
    """Test successful calculation of both values."""
    text = "This is a test text."
    expected_entropy = 0.25
    expected_coherence = 0.75
    test_model = "test-success-model"

    # Configure mock responses
    mock_instructor_client.chat.completions.create.side_effect = [
        EntropyResult(entropy=expected_entropy),    # First call (entropy)
        CoherenceResult(coherence=expected_coherence) # Second call (coherence)
    ]

    results = await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client,
        model_name=test_model
    )

    assert results.get("entropy") == expected_entropy
    assert results.get("coherence") == expected_coherence
    assert "error" not in results

    # Verify calls were made concurrently (or at least both were made)
    assert mock_instructor_client.chat.completions.create.call_count == 2
    calls = mock_instructor_client.chat.completions.create.call_args_list
    
    # Check arguments passed to the mock calls
    entropy_call_args = calls[0].kwargs
    coherence_call_args = calls[1].kwargs

    assert entropy_call_args['model'] == test_model
    assert entropy_call_args['response_model'] == EntropyResult
    assert entropy_call_args['messages'][0]['role'] == 'system' and "IRIS-E" in entropy_call_args['messages'][0]['content']
    assert entropy_call_args['messages'][1]['role'] == 'user' and text in entropy_call_args['messages'][1]['content']

    assert coherence_call_args['model'] == test_model
    assert coherence_call_args['response_model'] == CoherenceResult
    assert coherence_call_args['messages'][0]['role'] == 'system' and "IRIS-C" in coherence_call_args['messages'][0]['content']
    assert coherence_call_args['messages'][1]['role'] == 'user' and text in coherence_call_args['messages'][1]['content']


@pytest.mark.asyncio
async def test_calculate_epistemic_values_entropy_error(mock_instructor_client):
    """Test calculation when entropy call fails."""
    text = "Entropy fails."
    expected_coherence = 0.8

    # Configure mock responses: first call raises error, second succeeds
    mock_instructor_client.chat.completions.create.side_effect = [
        Exception("Entropy LLM failed"),
        CoherenceResult(coherence=expected_coherence)
    ]

    results = await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client
    )

    assert results.get("entropy") == 0.1 # Default fallback
    assert results.get("coherence") == expected_coherence
    assert "error" in results
    assert "Entropy Error: Entropy LLM failed" in results["error"]
    assert "Coherence Error" not in results["error"]
    assert mock_instructor_client.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_calculate_epistemic_values_coherence_error(mock_instructor_client):
    """Test calculation when coherence call fails."""
    text = "Coherence fails."
    expected_entropy = 0.3

    # Configure mock responses: first call succeeds, second raises error
    mock_instructor_client.chat.completions.create.side_effect = [
        EntropyResult(entropy=expected_entropy),
        Exception("Coherence LLM failed")
    ]

    results = await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client
    )

    assert results.get("entropy") == expected_entropy
    assert results.get("coherence") == 0.9 # Default fallback
    assert "error" in results
    assert "Coherence Error: Coherence LLM failed" in results["error"]
    assert "Entropy Error" not in results["error"]
    assert mock_instructor_client.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_calculate_epistemic_values_both_error(mock_instructor_client):
    """Test calculation when both calls fail."""
    text = "Both fail."

    # Configure mock responses: both calls raise errors
    mock_instructor_client.chat.completions.create.side_effect = [
        Exception("Entropy LLM failed"),
        Exception("Coherence LLM failed")
    ]

    results = await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client
    )

    assert results.get("entropy") == 0.1 # Default fallback
    assert results.get("coherence") == 0.9 # Default fallback
    assert "error" in results
    assert "Entropy Error: Entropy LLM failed" in results["error"]
    assert "Coherence Error: Coherence LLM failed" in results["error"]
    assert mock_instructor_client.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_calculate_epistemic_values_clamping(mock_instructor_client):
    """Test that results are clamped between 0.0 and 1.0."""
    text = "Test clamping."
    # Configure mock responses to return objects with out-of-bounds values
    mock_entropy_result = MagicMock(spec=EntropyResult)
    mock_entropy_result.entropy = 1.5
    mock_coherence_result = MagicMock(spec=CoherenceResult)
    mock_coherence_result.coherence = -0.5

    mock_instructor_client.chat.completions.create.side_effect = [
        mock_entropy_result,
        mock_coherence_result
    ]

    results = await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client
    )

    assert results.get("entropy") == 1.0 # Clamped from 1.5
    assert results.get("coherence") == 0.0 # Clamped from -0.5
    assert "error" not in results
    assert mock_instructor_client.chat.completions.create.call_count == 2

@pytest.mark.asyncio
async def test_calculate_epistemic_values_uses_default_model(mock_instructor_client):
    """Test that the default model name is used when none is provided."""
    text = "Default model test."
    # Configure mock responses
    mock_instructor_client.chat.completions.create.side_effect = [
        EntropyResult(entropy=0.1),
        CoherenceResult(coherence=0.9)
    ]

    await calculate_epistemic_values(
        text_to_evaluate=text,
        aclient=mock_instructor_client
        # No model_name provided
    )

    assert mock_instructor_client.chat.completions.create.call_count == 2
    calls = mock_instructor_client.chat.completions.create.call_args_list
    assert calls[0].kwargs['model'] == DEFAULT_OPENAI_MODEL_NAME
    assert calls[1].kwargs['model'] == DEFAULT_OPENAI_MODEL_NAME
