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
async def test_create_dsdma_from_profile_valid(monkeypatch):
    profile = types.SimpleNamespace(
        dsdma_identifier="DummyDSDMA",
        name="test-domain",
        dsdma_kwargs={"prompt_template": "tmpl", "domain_specific_knowledge": {"foo": "bar"}}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setitem(factory.DSDMA_CLASS_REGISTRY, "DummyDSDMA", DummyDSDMA)
    dsdma = await factory.create_dsdma_from_profile(profile, service_registry, model_name="m")
    assert isinstance(dsdma, DummyDSDMA)
    assert dsdma.domain_name == "test-domain"
    assert dsdma.model_name == "m"
    assert dsdma.prompt_template == "tmpl"
    assert dsdma.domain_specific_knowledge == {"foo": "bar"}

@pytest.mark.asyncio
async def test_create_dsdma_from_profile_none_profile(monkeypatch):
    default_profile = types.SimpleNamespace(
        dsdma_identifier="DummyDSDMA",
        name="default-domain",
        dsdma_kwargs={}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setitem(factory.DSDMA_CLASS_REGISTRY, "DummyDSDMA", DummyDSDMA)
    monkeypatch.setattr(factory, "load_profile", AsyncMock(return_value=default_profile))
    dsdma = await factory.create_dsdma_from_profile(None, service_registry)
    assert isinstance(dsdma, DummyDSDMA)
    assert dsdma.domain_name == "default-domain"

@pytest.mark.asyncio
async def test_create_dsdma_from_profile_missing_identifier(monkeypatch):
    profile = types.SimpleNamespace(
        dsdma_identifier=None,
        name="no-id-domain",
        dsdma_kwargs={}
    )
    default_profile = types.SimpleNamespace(
        dsdma_identifier="DummyDSDMA",
        name="default-domain",
        dsdma_kwargs={}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setitem(factory.DSDMA_CLASS_REGISTRY, "DummyDSDMA", DummyDSDMA)
    monkeypatch.setattr(factory, "load_profile", AsyncMock(return_value=default_profile))
    dsdma = await factory.create_dsdma_from_profile(profile, service_registry)
    assert isinstance(dsdma, DummyDSDMA)
    assert dsdma.domain_name == "default-domain"

@pytest.mark.asyncio
async def test_create_dsdma_from_profile_unknown_identifier(monkeypatch):
    profile = types.SimpleNamespace(
        dsdma_identifier="UnknownDSDMA",
        name="bad-domain",
        dsdma_kwargs={}
    )
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    dsdma = await factory.create_dsdma_from_profile(profile, service_registry)
    assert dsdma is None

@pytest.mark.asyncio
async def test_create_dsdma_from_profile_default_profile_missing(monkeypatch):
    monkeypatch.setattr(factory, "load_profile", AsyncMock(return_value=None))
    service_registry = ServiceRegistry()
    dummy_service = SimpleNamespace(get_client=lambda: None)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    dsdma = await factory.create_dsdma_from_profile(None, service_registry)
    assert dsdma is None
