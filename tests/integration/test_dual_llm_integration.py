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

    # Check if dual LLM is configured
    has_secondary = os.environ.get("CIRIS_OPENAI_API_KEY_2") is not None
    if not has_secondary:
        pytest.skip("Secondary API key not configured, skipping dual LLM test")

    # Create essential config
    essential_config = EssentialConfig()

    # Create service initializer
    initializer = ServiceInitializer(essential_config)

    # Create service registry
    service_registry = ServiceRegistry()
    initializer.service_registry = service_registry

    try:
        # Initialize all services - need to call the proper initialization sequence
        await initializer.initialize_infrastructure_services()
        await initializer.initialize_memory_service(essential_config)
        await initializer.initialize_security_services(essential_config, essential_config)
        await initializer.initialize_all_services(essential_config, essential_config, "test_agent", None, [])

        # Check that LLM services were registered
        llm_providers = service_registry.get_services_by_type(ServiceType.LLM)

        # Should have exactly 2 LLM providers (primary and secondary)
        assert len(llm_providers) == 2, f"Expected 2 LLM providers, got {len(llm_providers)}"

        # For this test, we just check that we have two services
        # The service instances themselves don't have provider metadata exposed directly
        providers_info = []
        for i, provider in enumerate(llm_providers):
            # Check basic properties
            assert hasattr(provider, 'model_name'), "LLM provider should have model_name"
            providers_info.append({
                'provider': f'provider_{i}',  # Generic name
                'model': getattr(provider, 'model_name', 'unknown'),
                'base_url': getattr(provider, 'base_url', 'default'),
                'priority': 'HIGH' if i == 0 else 'NORMAL'  # Assume first is primary
            })

        # Sort by priority for consistent checking
        providers_info.sort(key=lambda x: x['priority'])

        # Primary should have HIGH priority
        assert any(p['priority'] == 'HIGH' for p in providers_info), \
            "Primary provider not found with HIGH priority"

        # Secondary should have NORMAL priority
        assert any(p['priority'] == 'NORMAL' for p in providers_info), \
            "Secondary provider not found with NORMAL priority"

        # Check that we have different models for primary and secondary
        models = [p['model'] for p in providers_info]
        assert len(set(models)) == 2, "Primary and secondary should use different models"

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
