"""
Agent Configuration Service for self-configuration through graph memory.

Provides LOCAL vs IDENTITY scope handling with WA approval workflow
for identity-critical changes.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone

from ciris_engine.adapters.base import Service
from ciris_engine.schemas.graph_schemas_v1 import (
    GraphNode, GraphScope, NodeType, ConfigNodeType, CONFIG_SCOPE_MAP
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpResult, MemoryOpStatus
from ciris_engine.schemas.filter_schemas_v1 import AdaptiveFilterConfig

logger = logging.getLogger(__name__)


class AgentConfigService(Service):
    """Service for agent self-configuration through graph memory"""
    
    def __init__(self, memory_service: Any, wa_service: Any = None, filter_service: Any = None) -> None:
        super().__init__()
        self.memory = memory_service
        self.wa_service = wa_service
        self.filter_service = filter_service
        self._config_cache: Dict[str, Any] = {}
        self._pending_identity_updates: Dict[str, Any] = {}
        self._cache_ttl_minutes = 5
    
    async def start(self) -> None:
        """Start the configuration service"""
        await super().start()
        logger.info("Agent Configuration Service started")
    
    async def stop(self) -> None:
        """Stop the configuration service"""
        await super().stop()
        logger.info("Agent Configuration Service stopped")
    
    async def get_config(
        self, 
        config_type: ConfigNodeType,
        scope: Optional[GraphScope] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve configuration from graph memory with caching"""
        
        # Use default scope for config type if not specified
        if scope is None:
            scope = CONFIG_SCOPE_MAP.get(config_type, GraphScope.LOCAL)
        
        node_id = f"config/{config_type.value}"
        
        # Check cache first
        cache_key = f"{node_id}:{scope.value}"
        if cache_key in self._config_cache:
            cached = self._config_cache[cache_key]
            if cached["expires"] > datetime.now(timezone.utc):
                logger.debug(f"Config cache hit for {config_type.value}")
                return cached["data"]  # type: ignore[no-any-return]
            else:
                # Remove expired entry
                del self._config_cache[cache_key]
        
        # Fetch from memory
        node = GraphNode(
            id=node_id,
            type=NodeType.CONFIG,
            scope=scope
        )
        
        try:
            result = await self.memory.recall(node)
            if result.status == MemoryOpStatus.OK and result.data:
                config_data = result.data.get("attributes", {})
                
                # Cache for configured TTL
                self._config_cache[cache_key] = {
                    "data": config_data,
                    "expires": datetime.now(timezone.utc) + timedelta(minutes=self._cache_ttl_minutes)
                }
                
                logger.debug(f"Loaded config {config_type.value} from memory")
                return config_data  # type: ignore[no-any-return]
            else:
                logger.debug(f"No config found for {config_type.value}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving config {config_type.value}: {e}")
            return None
    
    async def update_config(
        self,
        config_type: ConfigNodeType,
        updates: Dict[str, Any],
        reason: str,
        thought_id: str,
        force_scope: Optional[GraphScope] = None
    ) -> MemoryOpResult:
        """Update configuration with automatic scope handling"""
        
        # Determine appropriate scope
        scope = force_scope or CONFIG_SCOPE_MAP.get(config_type, GraphScope.LOCAL)
        
        logger.info(f"Updating config {config_type.value} in {scope.value} scope: {reason}")
        
        # Check if this requires WA approval
        if scope == GraphScope.IDENTITY:
            return await self._handle_identity_update(
                config_type, updates, reason, thought_id
            )
        
        # LOCAL scope - can update immediately
        return await self._direct_update(config_type, updates, reason, scope)
    
    async def _handle_identity_update(
        self,
        config_type: ConfigNodeType,
        updates: Dict[str, Any],
        reason: str,
        thought_id: str
    ) -> MemoryOpResult:
        """Handle IDENTITY scope updates that require WA approval"""
        
        logger.warning(f"IDENTITY scope update requested for {config_type.value} - requires WA approval")
        
        # Store pending update
        pending_id = f"pending_identity_update_{thought_id}"
        self._pending_identity_updates[pending_id] = {
            "config_type": config_type,
            "updates": updates,
            "reason": reason,
            "thought_id": thought_id,
            "requested_at": datetime.now(timezone.utc),
            "status": "pending_wa_approval"
        }
        
        # Notify WA if service available
        if self.wa_service:
            try:
                await self.wa_service.send_deferral(
                    thought_id=thought_id,
                    reason=f"IDENTITY config update requested: {config_type.value} - {reason}. "
                           f"Updates: {updates}. Requires human approval for safety."
                )
                
                self._pending_identity_updates[pending_id]["status"] = "wa_notified"
                logger.info(f"WA notified of identity update request: {pending_id}")
                
            except Exception as e:
                logger.error(f"Failed to notify WA of identity update: {e}")
                self._pending_identity_updates[pending_id]["status"] = "wa_notification_failed"
        
        # Return pending status
        return MemoryOpResult(
            status=MemoryOpStatus.PENDING,
            reason=f"IDENTITY scope update requires WA approval. Pending ID: {pending_id}",
            data={"pending_id": pending_id}
        )
    
    async def _direct_update(
        self,
        config_type: ConfigNodeType,
        updates: Dict[str, Any],
        reason: str,
        scope: GraphScope
    ) -> MemoryOpResult:
        """Perform direct configuration update for LOCAL scope"""
        
        node_id = f"config/{config_type.value}"
        
        try:
            # Get current config or create new
            current_config = await self.get_config(config_type, scope) or {}
            
            # Apply updates
            updated_config = {**current_config, **updates}
            updated_config["last_updated"] = datetime.now(timezone.utc).isoformat()
            updated_config["update_reason"] = reason
            
            # Store updated config
            node = GraphNode(
                id=node_id,
                type=NodeType.CONFIG,
                scope=scope,
                attributes=updated_config,
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            
            result = await self.memory.memorize(node)
            
            if result.status == MemoryOpStatus.OK:
                # Invalidate cache
                cache_key = f"{node_id}:{scope.value}"
                if cache_key in self._config_cache:
                    del self._config_cache[cache_key]
                
                logger.info(f"Successfully updated config {config_type.value}")
                return result  # type: ignore[no-any-return]
            else:
                logger.error(f"Failed to update config {config_type.value}: {result.error}")
                return result  # type: ignore[no-any-return]
                
        except Exception as e:
            logger.error(f"Error updating config {config_type.value}: {e}")
            return MemoryOpResult(
                status=MemoryOpStatus.ERROR,
                error=str(e)
            )
    
    async def approve_identity_update(self, pending_id: str, approved: bool, approver: str) -> bool:
        """Approve or reject a pending identity update (called by WA)"""
        
        if pending_id not in self._pending_identity_updates:
            logger.warning(f"Pending identity update not found: {pending_id}")
            return False
        
        pending = self._pending_identity_updates[pending_id]
        
        if approved:
            logger.info(f"Identity update approved by {approver}: {pending_id}")
            
            # Perform the update
            result = await self._direct_update(
                pending["config_type"],
                pending["updates"],
                f"{pending['reason']} (approved by {approver})",
                GraphScope.IDENTITY
            )
            
            pending["status"] = "approved" if result.status == MemoryOpStatus.OK else "failed"
            pending["approved_by"] = approver
            pending["approved_at"] = datetime.now(timezone.utc)
            
            return result.status == MemoryOpStatus.OK
        
        else:
            logger.info(f"Identity update rejected by {approver}: {pending_id}")
            pending["status"] = "rejected"
            pending["rejected_by"] = approver
            pending["rejected_at"] = datetime.now(timezone.utc)
            
            return True
    
    async def get_pending_identity_updates(self) -> List[Dict[str, Any]]:
        """Get list of pending identity updates for WA review"""
        pending = []
        for pending_id, update in self._pending_identity_updates.items():
            if update["status"] in ["pending_wa_approval", "wa_notified"]:
                pending.append({
                    "pending_id": pending_id,
                    **update
                })
        return pending
    
    async def get_filter_config(self) -> Optional[AdaptiveFilterConfig]:
        """Convenience method to get filter configuration"""
        config_data = await self.get_config(ConfigNodeType.FILTER_CONFIG)
        if config_data:
            try:
                return AdaptiveFilterConfig(**config_data)
            except Exception as e:
                logger.error(f"Error parsing filter config: {e}")
                return None
        return None
    
    async def update_filter_config(
        self, 
        filter_config: AdaptiveFilterConfig, 
        reason: str, 
        thought_id: str
    ) -> MemoryOpResult:
        """Convenience method to update filter configuration"""
        return await self.update_config(
            ConfigNodeType.FILTER_CONFIG,
            filter_config.model_dump(),
            reason,
            thought_id
        )
    
    async def create_default_configs(self) -> Dict[ConfigNodeType, bool]:
        """Create default configurations for all config types"""
        results = {}
        
        for config_type in ConfigNodeType:
            try:
                existing = await self.get_config(config_type)
                if existing:
                    logger.debug(f"Config {config_type.value} already exists, skipping")
                    results[config_type] = True
                    continue
                
                default_config = await self._create_default_config(config_type)
                if default_config:
                    result = await self._direct_update(
                        config_type,
                        default_config,
                        "Initial default configuration",
                        CONFIG_SCOPE_MAP.get(config_type, GraphScope.LOCAL)
                    )
                    results[config_type] = result.status == MemoryOpStatus.OK
                else:
                    results[config_type] = False
                    
            except Exception as e:
                logger.error(f"Error creating default config for {config_type.value}: {e}")
                results[config_type] = False
        
        return results
    
    async def _create_default_config(self, config_type: ConfigNodeType) -> Optional[Dict[str, Any]]:
        """Create default configuration for a specific type"""
        
        if config_type == ConfigNodeType.FILTER_CONFIG:
            # Use filter service to create default config
            if self.filter_service:
                # This would integrate with the filter service
                return {
                    "version": 1,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "auto_adjust": True,
                    "new_user_threshold": 5
                }
        
        elif config_type == ConfigNodeType.BEHAVIOR_CONFIG:
            return {
                "personality_traits": ["helpful", "curious", "respectful"],
                "response_style": "friendly_professional",
                "proactivity_level": 0.5,
                "humor_enabled": True,
                "formality_level": "moderate"
            }
        
        elif config_type == ConfigNodeType.ETHICAL_BOUNDARIES:
            return {
                "harm_prevention": True,
                "privacy_protection": True,
                "truthfulness_required": True,
                "respect_autonomy": True,
                "fairness_principle": True
            }
        
        elif config_type == ConfigNodeType.CAPABILITY_LIMITS:
            return {
                "max_memory_operations": 100,
                "max_tool_calls_per_thought": 5,
                "max_response_length": 2000,
                "allowed_tool_categories": ["general", "memory", "communication"]
            }
        
        elif config_type == ConfigNodeType.TRUST_PARAMETERS:
            return {
                "initial_trust_score": 0.5,
                "trust_decay_rate": 0.1,
                "trust_boost_threshold": 5,
                "trust_violation_penalty": 0.2
            }
        
        elif config_type == ConfigNodeType.LEARNING_RULES:
            return {
                "learn_from_feedback": True,
                "adapt_response_style": True,
                "remember_preferences": True,
                "update_knowledge": False,  # Conservative default
                "modify_core_beliefs": False  # Requires explicit approval
            }
        
        # For other config types, return basic structure
        return {
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "enabled": True
        }
    
    async def get_config_health(self) -> Dict[str, Any]:
        """Get health status of configuration system"""
        health: Dict[str, Any] = {
            "healthy": True,
            "warnings": [],
            "errors": [],
            "cache_size": len(self._config_cache),
            "pending_identity_updates": len(self._pending_identity_updates)
        }
        
        # Check if critical configs exist
        critical_configs = [
            ConfigNodeType.FILTER_CONFIG,
            ConfigNodeType.ETHICAL_BOUNDARIES,
            ConfigNodeType.CAPABILITY_LIMITS
        ]
        
        for config_type in critical_configs:
            config = await self.get_config(config_type)
            if not config:
                health["warnings"].append(f"Missing critical config: {config_type.value}")
        
        # Check for old pending updates
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        old_pending = [
            pid for pid, update in self._pending_identity_updates.items()
            if update["requested_at"] < cutoff and update["status"] in ["pending_wa_approval", "wa_notified"]
        ]
        
        if old_pending:
            health["warnings"].append(f"{len(old_pending)} pending identity updates older than 24h")
        
        health["healthy"] = len(health["errors"]) == 0
        
        return health