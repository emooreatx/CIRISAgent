#!/usr/bin/env python3
"""
Comprehensive test for the mock LLM service to verify the AttributeError fix.
This test verifies that all response schemas generate valid JSON content
that can be parsed by the instructor library.
"""

import asyncio
import json
from tests.adapters.mock_llm import MockLLMClient
from ciris_engine.schemas.dma_results_v1 import (
    EthicalDMAResult, CSDMAResult, DSDMAResult, ActionSelectionResult
)
from ciris_engine.schemas.feedback_schemas_v1 import (
    OptimizationVetoResult, EpistemicHumilityResult
)
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult
from ciris_engine.dma.dsdma_base import BaseDSDMA

async def test_mock_llm_comprehensive():
    """Test that all mock responses have proper structure for instructor library."""
    client = MockLLMClient()
    
    # All schema types currently supported by the mock service
    test_schemas = [
        EthicalDMAResult,
        CSDMAResult, 
        DSDMAResult,
        BaseDSDMA.LLMOutputForDSDMA,
        OptimizationVetoResult,
        EpistemicHumilityResult,
        ActionSelectionResult,
        EntropyResult,
        CoherenceResult
    ]
    
    print("Testing mock LLM service with all supported schemas...")
    
    for schema in test_schemas:
        print(f"\nTesting {schema.__name__}...")
        
        # Create mock response
        response = await client._create(response_model=schema)
        
        # Verify the response is the correct type
        assert isinstance(response, schema), f"Expected {schema.__name__}, got {type(response)}"
        
        # Verify instructor-required attributes exist
        assert hasattr(response, 'choices'), f"{schema.__name__} missing 'choices' attribute"
        assert hasattr(response, 'finish_reason'), f"{schema.__name__} missing 'finish_reason' attribute"
        assert hasattr(response, '_raw_response'), f"{schema.__name__} missing '_raw_response' attribute"
        
        # Verify choice structure
        choice = response.choices[0]
        assert hasattr(choice, 'message'), f"{schema.__name__} choice missing 'message' attribute"
        assert hasattr(choice, 'finish_reason'), f"{schema.__name__} choice missing 'finish_reason' attribute"
        
        # Verify message structure
        message = choice.message
        assert hasattr(message, 'role'), f"{schema.__name__} message missing 'role' attribute"
        assert hasattr(message, 'content'), f"{schema.__name__} message missing 'content' attribute"
        assert message.role == "assistant", f"{schema.__name__} message role should be 'assistant', got '{message.role}'"
        
        # Verify content is valid JSON
        try:
            content_data = json.loads(message.content)
            print(f"  ✓ {schema.__name__}: Valid JSON content with keys: {list(content_data.keys())}")
        except json.JSONDecodeError as e:
            print(f"  ✗ {schema.__name__}: Invalid JSON content: {e}")
            print(f"    Content: {message.content}")
            raise
        
        # Verify the response can be used with Pydantic validation
        try:
            validated = schema(**content_data)
            print(f"  ✓ {schema.__name__}: Pydantic validation successful")
        except Exception as e:
            print(f"  ✗ {schema.__name__}: Pydantic validation failed: {e}")
            raise
    
    print(f"\n✅ All {len(test_schemas)} schema types passed comprehensive testing!")
    print("The AttributeError fix is working correctly.")

if __name__ == "__main__":
    asyncio.run(test_mock_llm_comprehensive())
