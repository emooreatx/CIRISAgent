"""
Unit tests for Agent Configuration Service
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from ciris_engine.services.agent_config_service import AgentConfigService
from ciris_engine.schemas.graph_schemas_v1 import (
    ConfigNodeType, GraphScope, CONFIG_SCOPE_MAP
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.filter_schemas_v1 import AdaptiveFilterConfig


@pytest.fixture
def mock_memory_service():
    """Mock memory service for testing"""
    mock = AsyncMock()
    mock.recall.return_value = MemoryOpResult(
        status=MemoryOpStatus.DENIED,
        reason="Config not found"
    )
    mock.memorize.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        reason="Saved successfully"
    )
    return mock


@pytest.fixture
def mock_wa_service():
    """Mock WA service for testing"""
    mock = AsyncMock()
    mock.send_deferral.return_value = True
    return mock


@pytest.fixture
def config_service(mock_memory_service, mock_wa_service):
    """Create config service instance for testing"""
    return AgentConfigService(mock_memory_service, mock_wa_service)


@pytest.mark.asyncio
async def test_config_service_initialization(config_service):
    """Test service initialization"""
    await config_service.start()
    
    # Should start without errors
    assert config_service.memory is not None
    assert config_service.wa_service is not None
    assert len(config_service._config_cache) == 0
    assert len(config_service._pending_identity_updates) == 0
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_get_config_not_found(config_service, mock_memory_service):
    """Test getting config that doesn't exist"""
    await config_service.start()
    
    result = await config_service.get_config(ConfigNodeType.FILTER_CONFIG)
    
    assert result is None
    mock_memory_service.recall.assert_called_once()
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_get_config_found(mock_memory_service, mock_wa_service):
    """Test getting existing config"""
    # Mock existing config
    test_config = {"version": 1, "enabled": True}
    mock_memory_service.recall.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data={"attributes": test_config}
    )
    
    service = AgentConfigService(mock_memory_service, mock_wa_service)
    await service.start()
    
    result = await service.get_config(ConfigNodeType.FILTER_CONFIG)
    
    assert result == test_config
    assert len(service._config_cache) == 1  # Should be cached
    
    # Second call should use cache
    result2 = await service.get_config(ConfigNodeType.FILTER_CONFIG)
    assert result2 == test_config
    assert mock_memory_service.recall.call_count == 1  # No additional calls
    
    await service.stop()


@pytest.mark.asyncio
async def test_config_cache_expiry(mock_memory_service, mock_wa_service):
    """Test config cache expiry"""
    test_config = {"version": 1, "enabled": True}
    mock_memory_service.recall.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data={"attributes": test_config}
    )
    
    service = AgentConfigService(mock_memory_service, mock_wa_service)
    service._cache_ttl_minutes = 0.001  # Very short TTL for testing
    await service.start()
    
    # Get config (will cache)
    result1 = await service.get_config(ConfigNodeType.FILTER_CONFIG)
    assert result1 == test_config
    
    # Wait for cache to expire
    await asyncio.sleep(0.1)
    
    # Get config again (should fetch from memory again)
    result2 = await service.get_config(ConfigNodeType.FILTER_CONFIG)
    assert result2 == test_config
    assert mock_memory_service.recall.call_count == 2
    
    await service.stop()


@pytest.mark.asyncio
async def test_update_local_config(config_service, mock_memory_service):
    """Test updating LOCAL scope configuration"""
    await config_service.start()
    
    updates = {"new_setting": "value", "enabled": True}
    
    result = await config_service.update_config(
        ConfigNodeType.FILTER_CONFIG,
        updates,
        "Test update",
        "thought123"
    )
    
    assert result.status == MemoryOpStatus.OK
    mock_memory_service.memorize.assert_called_once()
    
    # Verify the saved data
    call_args = mock_memory_service.memorize.call_args[0][0]
    assert call_args.scope == GraphScope.LOCAL
    assert call_args.type.value == "config"
    assert "new_setting" in call_args.attributes
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_update_identity_config_requires_approval(config_service, mock_wa_service):
    """Test updating IDENTITY scope configuration requires WA approval"""
    await config_service.start()
    
    updates = {"personality": "more_helpful"}
    
    result = await config_service.update_config(
        ConfigNodeType.BEHAVIOR_CONFIG,  # IDENTITY scope
        updates,
        "Change personality",
        "thought456"
    )
    
    assert result.status == MemoryOpStatus.PENDING
    assert "pending_identity_update_thought456" in result.data["pending_id"]
    
    # Should notify WA
    mock_wa_service.send_deferral.assert_called_once()
    
    # Should be in pending updates
    assert len(config_service._pending_identity_updates) == 1
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_approve_identity_update(config_service, mock_memory_service):
    """Test approving a pending identity update"""
    await config_service.start()
    
    # Create pending update
    updates = {"new_boundary": "no_violence"}
    await config_service.update_config(
        ConfigNodeType.ETHICAL_BOUNDARIES,
        updates,
        "Add boundary",
        "thought789"
    )
    
    pending_id = "pending_identity_update_thought789"
    
    # Approve the update
    success = await config_service.approve_identity_update(
        pending_id, 
        approved=True, 
        approver="human_supervisor"
    )
    
    assert success == True
    
    # Should have called memorize to save the config
    mock_memory_service.memorize.assert_called()
    
    # Verify update status
    pending = config_service._pending_identity_updates[pending_id]
    assert pending["status"] == "approved"
    assert pending["approved_by"] == "human_supervisor"
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_reject_identity_update(config_service):
    """Test rejecting a pending identity update"""
    await config_service.start()
    
    # Create pending update
    updates = {"dangerous_setting": "enabled"}
    await config_service.update_config(
        ConfigNodeType.CAPABILITY_LIMITS,
        updates,
        "Dangerous change",
        "thought999"
    )
    
    pending_id = "pending_identity_update_thought999"
    
    # Reject the update
    success = await config_service.approve_identity_update(
        pending_id,
        approved=False,
        approver="safety_supervisor"
    )
    
    assert success == True
    
    # Verify update status
    pending = config_service._pending_identity_updates[pending_id]
    assert pending["status"] == "rejected"
    assert pending["rejected_by"] == "safety_supervisor"
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_get_pending_identity_updates(config_service):
    """Test getting pending identity updates"""
    await config_service.start()
    
    # Create multiple pending updates
    await config_service.update_config(
        ConfigNodeType.BEHAVIOR_CONFIG,
        {"trait": "funny"},
        "Add humor",
        "thought1"
    )
    
    await config_service.update_config(
        ConfigNodeType.ETHICAL_BOUNDARIES,
        {"rule": "be_nice"},
        "Add niceness rule",
        "thought2"
    )
    
    pending = await config_service.get_pending_identity_updates()
    
    assert len(pending) == 2
    assert all("pending_id" in update for update in pending)
    assert all(update["status"] in ["pending_wa_approval", "wa_notified"] for update in pending)
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_create_default_configs(config_service, mock_memory_service):
    """Test creating default configurations"""
    await config_service.start()
    
    results = await config_service.create_default_configs()
    
    # Should attempt to create configs for all config types
    assert len(results) == len(ConfigNodeType)
    
    # All should succeed (since mock always returns OK)
    assert all(results.values())
    
    # Should have called memorize for each config type
    assert mock_memory_service.memorize.call_count == len(ConfigNodeType)
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_create_default_configs_skips_existing(mock_memory_service, mock_wa_service):
    """Test that default config creation skips existing configs"""
    # Mock that some configs already exist
    def mock_recall(node):
        if "filter_config" in node.id:
            return MemoryOpResult(
                status=MemoryOpStatus.OK,
                data={"attributes": {"existing": True}}
            )
        return MemoryOpResult(status=MemoryOpStatus.DENIED)
    
    mock_memory_service.recall.side_effect = mock_recall
    
    service = AgentConfigService(mock_memory_service, mock_wa_service)
    await service.start()
    
    results = await service.create_default_configs()
    
    # Filter config should be skipped (True but not created)
    assert results[ConfigNodeType.FILTER_CONFIG] == True
    
    # Others should be created
    assert all(results[ct] for ct in ConfigNodeType if ct != ConfigNodeType.FILTER_CONFIG)
    
    # Should not call memorize for filter config
    memorize_calls = mock_memory_service.memorize.call_args_list
    filter_calls = [call for call in memorize_calls if "filter_config" in str(call)]
    assert len(filter_calls) == 0
    
    await service.stop()


@pytest.mark.asyncio
async def test_get_filter_config_convenience(mock_memory_service, mock_wa_service):
    """Test convenience method for getting filter config"""
    # Mock filter config
    filter_data = AdaptiveFilterConfig(version=2).model_dump()
    mock_memory_service.recall.return_value = MemoryOpResult(
        status=MemoryOpStatus.OK,
        data={"attributes": filter_data}
    )
    
    service = AgentConfigService(mock_memory_service, mock_wa_service)
    await service.start()
    
    filter_config = await service.get_filter_config()
    
    assert isinstance(filter_config, AdaptiveFilterConfig)
    assert filter_config.version == 2
    
    await service.stop()


@pytest.mark.asyncio
async def test_update_filter_config_convenience(config_service):
    """Test convenience method for updating filter config"""
    await config_service.start()
    
    filter_config = AdaptiveFilterConfig(version=3)
    
    result = await config_service.update_filter_config(
        filter_config,
        "Update filter settings",
        "thought123"
    )
    
    assert result.status == MemoryOpStatus.OK
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_config_health_monitoring(config_service):
    """Test configuration health monitoring"""
    await config_service.start()
    
    health = await config_service.get_config_health()
    
    assert "healthy" in health
    assert "warnings" in health
    assert "errors" in health
    assert "cache_size" in health
    assert "pending_identity_updates" in health
    
    # Should warn about missing critical configs
    assert len(health["warnings"]) > 0  # Missing configs
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_config_scope_mapping():
    """Test that config scope mapping is correct"""
    assert CONFIG_SCOPE_MAP[ConfigNodeType.FILTER_CONFIG] == GraphScope.LOCAL
    assert CONFIG_SCOPE_MAP[ConfigNodeType.BEHAVIOR_CONFIG] == GraphScope.IDENTITY
    assert CONFIG_SCOPE_MAP[ConfigNodeType.ETHICAL_BOUNDARIES] == GraphScope.IDENTITY
    
    # All LOCAL scope configs should be updatable without approval
    local_configs = [ct for ct, scope in CONFIG_SCOPE_MAP.items() if scope == GraphScope.LOCAL]
    assert ConfigNodeType.FILTER_CONFIG in local_configs
    assert ConfigNodeType.CHANNEL_CONFIG in local_configs
    
    # All IDENTITY scope configs should require approval  
    identity_configs = [ct for ct, scope in CONFIG_SCOPE_MAP.items() if scope == GraphScope.IDENTITY]
    assert ConfigNodeType.BEHAVIOR_CONFIG in identity_configs
    assert ConfigNodeType.ETHICAL_BOUNDARIES in identity_configs


@pytest.mark.asyncio
async def test_error_handling(config_service, mock_memory_service):
    """Test error handling in various scenarios"""
    await config_service.start()
    
    # Test memory service error
    mock_memory_service.recall.side_effect = Exception("Memory service down")
    
    result = await config_service.get_config(ConfigNodeType.FILTER_CONFIG)
    assert result is None  # Should handle error gracefully
    
    # Test memory save error
    mock_memory_service.memorize.side_effect = Exception("Save failed")
    
    result = await config_service.update_config(
        ConfigNodeType.FILTER_CONFIG,
        {"test": "value"},
        "Test update",
        "thought123"
    )
    
    assert result.status == MemoryOpStatus.ERROR
    assert "Save failed" in result.error
    
    await config_service.stop()


@pytest.mark.asyncio
async def test_wa_service_not_available(mock_memory_service):
    """Test behavior when WA service is not available"""
    service = AgentConfigService(mock_memory_service, wa_service=None)
    await service.start()
    
    # Identity update without WA service
    result = await service.update_config(
        ConfigNodeType.BEHAVIOR_CONFIG,
        {"personality": "helpful"},
        "Update personality", 
        "thought123"
    )
    
    assert result.status == MemoryOpStatus.PENDING
    
    # Should still create pending update even without WA
    assert len(service._pending_identity_updates) == 1
    
    await service.stop()