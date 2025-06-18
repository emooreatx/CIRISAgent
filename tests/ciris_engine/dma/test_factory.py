import pytest
import types
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace
from ciris_engine.registries.base import ServiceRegistry, Priority
from pathlib import Path

import ciris_engine.dma.factory as factory

class DummyDSDMA(factory.BaseDSDMA):
    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        super().__init__(*args, **kwargs)

@pytest.mark.asyncio
async def test_create_dsdma_from_identity_valid(monkeypatch):
    identity = types.SimpleNamespace(
        dsdma_identifier="DummyDSDMA",
        name="test-domain",
        dsdma_kwargs={"prompt_template": "tmpl", "domain_specific_knowledge": {"foo": "bar"}}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setitem(factory.DSDMA_CLASS_REGISTRY, "DummyDSDMA", DummyDSDMA)
    dsdma = await factory.create_dsdma_from_identity(identity, service_registry, model_name="m")
    # Factory now always returns BaseDSDMA, not custom classes
    assert isinstance(dsdma, factory.BaseDSDMA)
    assert dsdma.domain_name == "test-domain"
    assert dsdma.model_name == "m"
    assert dsdma.prompt_template == "tmpl"
    assert dsdma.domain_specific_knowledge == {"foo": "bar"}

@pytest.mark.asyncio
async def test_create_dsdma_from_identity_none_raises_error(monkeypatch):
    # Test that passing None identity raises an error
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    
    # Factory now raises error when identity is None - agent has no identity
    with pytest.raises(RuntimeError, match="Cannot create DSDMA without agent identity"):
        await factory.create_dsdma_from_identity(None, service_registry)

@pytest.mark.asyncio
async def test_create_dsdma_from_identity_missing_identifier(monkeypatch):
    # Test with identity that has no dsdma_identifier (which is fine since we always use BaseDSDMA)
    identity = types.SimpleNamespace(
        dsdma_identifier=None,
        name="no-id-domain",
        dsdma_kwargs={}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    dsdma = await factory.create_dsdma_from_identity(identity, service_registry)
    assert isinstance(dsdma, factory.BaseDSDMA)
    assert dsdma.domain_name == "no-id-domain"

@pytest.mark.asyncio
async def test_create_dsdma_from_identity_always_uses_base_dsdma(monkeypatch):
    # Test that even with unknown identifier, it still creates BaseDSDMA
    identity = types.SimpleNamespace(
        dsdma_identifier="UnknownDSDMA",
        name="any-domain",
        dsdma_kwargs={}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    dsdma = await factory.create_dsdma_from_identity(identity, service_registry)
    assert isinstance(dsdma, factory.BaseDSDMA)
    assert dsdma.domain_name == "any-domain"

