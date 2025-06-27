"""
Integration test for dual LLM service functionality.
Tests actual initialization with environment variables.
"""
import os
import pytest
import asyncio
from ciris_engine.logic.runtime.service_initializer import ServiceInitializer
from ciris_engine.schemas.config.essential import EssentialConfig
from ciris_engine.logic.registries.base import ServiceRegistry
from ciris_engine.schemas.runtime.enums import ServiceType


@pytest.mark.asyncio
async def test_dual_llm_service_real_initialization():
    """Test real initialization with dual LLM services from environment."""
    # Ensure environment variables are set
    assert os.environ.get("OPENAI_API_KEY"), "Primary API key not found"
    assert os.environ.get("CIRIS_OPENAI_API_KEY_2"), "Secondary API key not found"
    
    # Create essential config
    essential_config = EssentialConfig()
    
    # Create service initializer
    initializer = ServiceInitializer(essential_config)
    
    # Create service registry
    service_registry = ServiceRegistry()
    initializer.service_registry = service_registry
    
    try:
        # Initialize services
        await initializer.initialize_services()
        
        # Check that LLM services were registered
        llm_providers = service_registry.get_all_providers(ServiceType.LLM)
        
        # Should have exactly 2 LLM providers
        assert len(llm_providers) == 2, f"Expected 2 LLM providers, got {len(llm_providers)}"
        
        # Check metadata of providers
        providers_info = []
        for provider_entry in llm_providers:
            provider, priority, metadata = provider_entry
            providers_info.append({
                'provider': metadata.get('provider'),
                'model': metadata.get('model'),
                'base_url': metadata.get('base_url'),
                'priority': priority.name
            })
        
        # Sort by priority for consistent checking
        providers_info.sort(key=lambda x: x['priority'])
        
        # Primary should have HIGH priority
        assert any(p['priority'] == 'HIGH' and p['provider'] == 'openai' for p in providers_info), \
            "Primary provider not found with HIGH priority"
        
        # Secondary should have NORMAL priority
        assert any(p['priority'] == 'NORMAL' and p['provider'] == 'openai_secondary' for p in providers_info), \
            "Secondary provider not found with NORMAL priority"
        
        # Secondary should have Lambda AI base URL
        secondary = next((p for p in providers_info if p['provider'] == 'openai_secondary'), None)
        assert secondary is not None
        assert 'lambda.ai' in secondary.get('base_url', ''), \
            f"Expected Lambda AI URL in secondary provider, got {secondary.get('base_url')}"
        
        print("\nDual LLM Service Configuration:")
        for info in providers_info:
            print(f"  {info['provider']}: {info['model']} at {info.get('base_url', 'default')} (Priority: {info['priority']})")
        
    finally:
        # Cleanup
        if hasattr(initializer, 'shutdown_service') and initializer.shutdown_service:
            await initializer.shutdown_service.request_shutdown("Test complete")
        
        # Stop all services
        if hasattr(initializer, 'llm_service') and initializer.llm_service:
            if hasattr(initializer.llm_service, 'stop'):
                await initializer.llm_service.stop()


if __name__ == "__main__":
    # Run the test directly
    asyncio.run(test_dual_llm_service_real_initialization())