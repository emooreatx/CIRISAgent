"""
Runtime Adapter Management

Provides dynamic adapter loading/unloading capabilities during runtime,
extending the existing processor control capabilities with adapter lifecycle management.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration
from ciris_engine.adapters import load_adapter
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile
from ciris_engine.config.config_loader import ConfigLoader
from ciris_engine.registries.base import ServiceRegistry


logger = logging.getLogger(__name__)


@dataclass
class AdapterInstance:
    """Information about a loaded adapter instance"""
    adapter_id: str
    mode: str
    adapter: PlatformAdapter
    config_params: Dict[str, Any]
    loaded_at: datetime
    is_running: bool = False
    services_registered: List[str] = None

    def __post_init__(self):
        if self.services_registered is None:
            self.services_registered = []


class AdapterManagerInterface:
    """Interface for runtime adapter management operations"""
    
    async def load_adapter(self, mode: str, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> bool:
        """Load and start a new adapter instance"""
        ...
    
    async def unload_adapter(self, adapter_id: str) -> bool:
        """Stop and unload an adapter instance"""
        ...
    
    async def reload_adapter(self, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> bool:
        """Reload an adapter with new configuration"""
        ...
    
    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapter instances"""
        ...
    
    async def get_adapter_status(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific adapter"""
        ...


class RuntimeAdapterManager(AdapterManagerInterface):
    """Manages runtime adapter lifecycle with configuration support"""
    
    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.loaded_adapters: Dict[str, AdapterInstance] = {}
        self._adapter_counter = 0
        
    async def load_adapter(self, mode: str, adapter_id: Optional[str] = None, config_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load and start a new adapter instance
        
        Args:
            mode: Adapter type (cli, discord, api, etc.)
            adapter_id: Optional unique ID, auto-generated if not provided
            config_params: Optional configuration parameters
            
        Returns:
            Dict with adapter_id, status, and details
        """
        try:
            # Generate adapter ID if not provided
            if not adapter_id:
                self._adapter_counter += 1
                adapter_id = f"{mode}_{self._adapter_counter}"
            
            # Check if adapter ID already exists
            if adapter_id in self.loaded_adapters:
                return {
                    "success": False,
                    "error": f"Adapter with ID '{adapter_id}' already exists"
                }
            
            logger.info(f"Loading adapter: mode={mode}, id={adapter_id}, params={config_params}")
            
            # Load adapter class
            adapter_class = load_adapter(mode)
            
            # Create adapter instance with config
            adapter_kwargs = config_params or {}
            adapter = adapter_class(self.runtime, **adapter_kwargs)
            
            # Create adapter instance record
            instance = AdapterInstance(
                adapter_id=adapter_id,
                mode=mode,
                adapter=adapter,
                config_params=adapter_kwargs,
                loaded_at=datetime.now(timezone.utc)
            )
            
            # Start the adapter
            await adapter.start()
            instance.is_running = True
            
            # Register adapter services
            await self._register_adapter_services(instance)
            
            # Add to runtime adapters list
            self.runtime.adapters.append(adapter)
            self.loaded_adapters[adapter_id] = instance
            
            logger.info(f"Successfully loaded and started adapter {adapter_id}")
            
            return {
                "success": True,
                "adapter_id": adapter_id,
                "mode": mode,
                "services_registered": len(instance.services_registered),
                "loaded_at": instance.loaded_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to load adapter {mode} with ID {adapter_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def unload_adapter(self, adapter_id: str) -> Dict[str, Any]:
        """Stop and unload an adapter instance
        
        Args:
            adapter_id: Unique identifier of the adapter to unload
            
        Returns:
            Dict with success status and details
        """
        try:
            if adapter_id not in self.loaded_adapters:
                return {
                    "success": False,
                    "error": f"Adapter with ID '{adapter_id}' not found"
                }
            
            instance = self.loaded_adapters[adapter_id]
            logger.info(f"Unloading adapter {adapter_id}")
            
            # Stop the adapter
            if instance.is_running:
                await instance.adapter.stop()
                instance.is_running = False
            
            # Unregister services
            await self._unregister_adapter_services(instance)
            
            # Remove from runtime adapters list
            if instance.adapter in self.runtime.adapters:
                self.runtime.adapters.remove(instance.adapter)
            
            # Remove from loaded adapters
            del self.loaded_adapters[adapter_id]
            
            logger.info(f"Successfully unloaded adapter {adapter_id}")
            
            return {
                "success": True,
                "adapter_id": adapter_id,
                "mode": instance.mode,
                "services_unregistered": len(instance.services_registered),
                "was_running": True
            }
            
        except Exception as e:
            logger.error(f"Failed to unload adapter {adapter_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def reload_adapter(self, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Reload an adapter with new configuration
        
        Args:
            adapter_id: Unique identifier of the adapter to reload
            config_params: New configuration parameters
            
        Returns:
            Dict with success status and details
        """
        try:
            if adapter_id not in self.loaded_adapters:
                return {
                    "success": False,
                    "error": f"Adapter with ID '{adapter_id}' not found"
                }
            
            instance = self.loaded_adapters[adapter_id]
            mode = instance.mode
            
            logger.info(f"Reloading adapter {adapter_id} with new config")
            
            # Unload the existing adapter
            unload_result = await self.unload_adapter(adapter_id)
            if not unload_result["success"]:
                return unload_result
            
            # Load with new configuration
            load_result = await self.load_adapter(mode, adapter_id, config_params)
            
            if load_result["success"]:
                logger.info(f"Successfully reloaded adapter {adapter_id}")
            
            return load_result
            
        except Exception as e:
            logger.error(f"Failed to reload adapter {adapter_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapter instances
        
        Returns:
            List of adapter information dictionaries
        """
        try:
            adapters = []
            for adapter_id, instance in self.loaded_adapters.items():
                # Get health status
                health_status = "unknown"
                try:
                    if hasattr(instance.adapter, 'is_healthy'):
                        is_healthy = await instance.adapter.is_healthy()
                        health_status = "healthy" if is_healthy else "error"
                    elif instance.is_running:
                        health_status = "active"
                    else:
                        health_status = "stopped"
                except Exception:
                    health_status = "error"
                
                adapters.append({
                    "adapter_id": adapter_id,
                    "mode": instance.mode,
                    "is_running": instance.is_running,
                    "health_status": health_status,
                    "services_count": len(instance.services_registered),
                    "loaded_at": instance.loaded_at.isoformat(),
                    "config_params": instance.config_params
                })
            
            return adapters
            
        except Exception as e:
            logger.error(f"Failed to list adapters: {e}", exc_info=True)
            return []
    
    async def get_adapter_status(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific adapter
        
        Args:
            adapter_id: Unique identifier of the adapter
            
        Returns:
            Dict with detailed adapter status information
        """
        try:
            if adapter_id not in self.loaded_adapters:
                return {
                    "found": False,
                    "error": f"Adapter with ID '{adapter_id}' not found"
                }
            
            instance = self.loaded_adapters[adapter_id]
            
            # Get health status
            health_status = "unknown"
            health_details = {}
            try:
                if hasattr(instance.adapter, 'is_healthy'):
                    is_healthy = await instance.adapter.is_healthy()
                    health_status = "healthy" if is_healthy else "error"
                elif instance.is_running:
                    health_status = "active"
                else:
                    health_status = "stopped"
            except Exception as e:
                health_status = "error"
                health_details["error"] = str(e)
            
            # Get service registration details
            service_details = []
            try:
                registrations = instance.adapter.get_services_to_register()
                for reg in registrations:
                    service_details.append({
                        "service_type": reg.service_type.value,
                        "priority": reg.priority.name,
                        "handlers": reg.handlers,
                        "capabilities": reg.capabilities
                    })
            except Exception as e:
                service_details = [{"error": f"Failed to get service registrations: {e}"}]
            
            uptime_seconds = (datetime.now(timezone.utc) - instance.loaded_at).total_seconds()
            
            return {
                "found": True,
                "adapter_id": adapter_id,
                "mode": instance.mode,
                "is_running": instance.is_running,
                "health_status": health_status,
                "health_details": health_details,
                "loaded_at": instance.loaded_at.isoformat(),
                "uptime_seconds": uptime_seconds,
                "config_params": instance.config_params,
                "services_registered": instance.services_registered,
                "service_details": service_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get adapter status for {adapter_id}: {e}", exc_info=True)
            return {
                "found": False,
                "error": str(e)
            }
    
    async def load_adapter_from_profile(self, profile_name: str, adapter_id: Optional[str] = None) -> Dict[str, Any]:
        """Load adapter configuration from an agent profile
        
        Args:
            profile_name: Name of the agent profile to load
            adapter_id: Optional unique ID for the adapter
            
        Returns:
            Dict with load results
        """
        try:
            # Load the profile configuration
            config = await ConfigLoader.load_config(profile_name=profile_name)
            
            if not config.agent_profiles or profile_name not in config.agent_profiles:
                return {
                    "success": False,
                    "error": f"Profile '{profile_name}' not found in configuration"
                }
            
            profile = config.agent_profiles[profile_name]
            results = []
            
            # Load Discord adapter if configured
            if profile.discord_config:
                discord_params = {
                    "channel_id": profile.discord_config.home_channel_id,
                    "bot_token": profile.discord_config.bot_token
                }
                result = await self.load_adapter("discord", adapter_id or f"discord_{profile_name}", discord_params)
                results.append({"adapter_type": "discord", **result})
            
            # Load API adapter if configured
            if profile.api_config:
                api_params = {
                    "host": profile.api_config.host,
                    "port": profile.api_config.port
                }
                result = await self.load_adapter("api", adapter_id or f"api_{profile_name}", api_params)
                results.append({"adapter_type": "api", **result})
            
            # Load CLI adapter if configured
            if profile.cli_config:
                cli_params = {}
                result = await self.load_adapter("cli", adapter_id or f"cli_{profile_name}", cli_params)
                results.append({"adapter_type": "cli", **result})
            
            success_count = sum(1 for r in results if r.get("success", False))
            
            return {
                "success": success_count > 0,
                "profile_name": profile_name,
                "adapters_loaded": success_count,
                "total_attempted": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Failed to load adapters from profile {profile_name}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _register_adapter_services(self, instance: AdapterInstance) -> None:
        """Register services for an adapter instance"""
        try:
            if not self.runtime.service_registry:
                logger.error("ServiceRegistry not initialized. Cannot register adapter services.")
                return
            
            registrations = instance.adapter.get_services_to_register()
            for reg in registrations:
                if not isinstance(reg, ServiceRegistration):
                    logger.error(f"Adapter {instance.adapter.__class__.__name__} provided invalid ServiceRegistration: {reg}")
                    continue
                
                service_key = f"{reg.service_type.value}:{reg.provider.__class__.__name__}"
                
                if reg.handlers:  # Register for specific handlers
                    for handler_name in reg.handlers:
                        self.runtime.service_registry.register(
                            handler=handler_name,
                            service_type=reg.service_type.value,
                            provider=reg.provider,
                            priority=reg.priority,
                            capabilities=reg.capabilities
                        )
                        instance.services_registered.append(f"{handler_name}:{service_key}")
                else:  # Register globally
                    self.runtime.service_registry.register_global(
                        service_type=reg.service_type.value,
                        provider=reg.provider,
                        priority=reg.priority,
                        capabilities=reg.capabilities
                    )
                    instance.services_registered.append(f"global:{service_key}")
                
                logger.info(f"Registered {service_key} from adapter {instance.adapter_id}")
                
        except Exception as e:
            logger.error(f"Error registering services for adapter {instance.adapter_id}: {e}", exc_info=True)
    
    async def _unregister_adapter_services(self, instance: AdapterInstance) -> None:
        """Unregister services for an adapter instance"""
        try:
            if not self.runtime.service_registry:
                logger.warning("ServiceRegistry not available. Cannot unregister adapter services.")
                return
            
            # Note: ServiceRegistry doesn't currently have explicit unregister methods
            # This would need to be implemented in the registry to properly clean up
            # For now, we just log what would be unregistered
            for service_key in instance.services_registered:
                logger.info(f"Would unregister service: {service_key} from adapter {instance.adapter_id}")
            
            instance.services_registered.clear()
            
        except Exception as e:
            logger.error(f"Error unregistering services for adapter {instance.adapter_id}: {e}", exc_info=True)
