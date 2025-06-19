"""
Runtime Adapter Management

Provides dynamic adapter loading/unloading capabilities during runtime,
extending the existing processor control capabilities with adapter lifecycle management.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ciris_engine.protocols.adapter_interface import PlatformAdapter, ServiceRegistration
from ciris_engine.adapters import load_adapter
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentTemplate
from ciris_engine.config.config_loader import ConfigLoader
from ciris_engine.registries.base import ServiceRegistry


logger = logging.getLogger(__name__)


@dataclass
class AdapterInstance:
    """Information about a loaded adapter instance"""
    adapter_id: str
    adapter_type: str
    adapter: PlatformAdapter
    config_params: Dict[str, Any]
    loaded_at: datetime
    is_running: bool = False
    services_registered: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # services_registered is now properly initialized with default_factory
        pass


class AdapterManagerInterface:
    """Interface for runtime adapter management operations"""
    
    async def load_adapter(self, adapter_type: str, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load and start a new adapter instance"""
        raise NotImplementedError("This is an interface method")
    
    async def unload_adapter(self, adapter_id: str) -> Dict[str, Any]:
        """Stop and unload an adapter instance"""
        raise NotImplementedError("This is an interface method")
    
    async def reload_adapter(self, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Reload an adapter with new configuration"""
        raise NotImplementedError("This is an interface method")
    
    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapter instances"""
        raise NotImplementedError("This is an interface method")
    
    async def get_adapter_status(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed status of a specific adapter"""
        raise NotImplementedError("This is an interface method")


class RuntimeAdapterManager(AdapterManagerInterface):
    """Manages runtime adapter lifecycle with configuration support"""
    
    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.loaded_adapters: Dict[str, AdapterInstance] = {}
        self._adapter_counter = 0
        
    async def load_adapter(self, adapter_type: str, adapter_id: str, config_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load and start a new adapter instance
        
        Args:
            adapter_type: Adapter type (cli, discord, api, etc.)
            adapter_id: Unique ID for the adapter
            config_params: Optional configuration parameters
            
        Returns:
            Dict with success status and details
        """
        try:
            if adapter_id in self.loaded_adapters:
                logger.warning(f"Adapter with ID '{adapter_id}' already exists")
                return {
                    "success": False,
                    "error": f"Adapter with ID '{adapter_id}' already exists"
                }
            
            logger.info(f"Loading adapter: type={adapter_type}, id={adapter_id}, params={config_params}")
            
            adapter_class = load_adapter(adapter_type)
            
            adapter_kwargs = config_params or {}
            adapter = adapter_class(self.runtime, **adapter_kwargs)
            
            instance = AdapterInstance(
                adapter_id=adapter_id,
                adapter_type=adapter_type,
                adapter=adapter,
                config_params=adapter_kwargs,
                loaded_at=datetime.now(timezone.utc)
            )
            
            await adapter.start()
            instance.is_running = True
            
            await self._register_adapter_services(instance)
            
            self.runtime.adapters.append(adapter)
            self.loaded_adapters[adapter_id] = instance
            
            logger.info(f"Successfully loaded and started adapter {adapter_id}")
            return {
                "success": True,
                "adapter_id": adapter_id,
                "adapter_type": adapter_type,
                "services_registered": len(instance.services_registered),
                "loaded_at": instance.loaded_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to load adapter {adapter_type} with ID {adapter_id}: {e}", exc_info=True)
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
                    "adapter_id": adapter_id,
                    "error": f"Adapter with ID '{adapter_id}' not found"
                }
            
            instance = self.loaded_adapters[adapter_id]
            
            communication_adapter_types = {"discord", "api", "cli"}
            if instance.adapter_type in communication_adapter_types:
                remaining_comm_adapters = sum(
                    1 for aid, inst in self.loaded_adapters.items() 
                    if aid != adapter_id and inst.adapter_type in communication_adapter_types
                )
                
                if remaining_comm_adapters == 0:
                    return {
                        "success": False,
                        "adapter_id": adapter_id,
                        "adapter_type": instance.adapter_type,
                        "error": f"Cannot unload {adapter_id}: it is one of the last communication-capable adapters"
                    }
            
            logger.info(f"Unloading adapter {adapter_id}")
            
            if instance.is_running:
                await instance.adapter.stop()
                instance.is_running = False
            
            await self._unregister_adapter_services(instance)
            
            if instance.adapter in self.runtime.adapters:
                self.runtime.adapters.remove(instance.adapter)
            
            del self.loaded_adapters[adapter_id]
            
            logger.info(f"Successfully unloaded adapter {adapter_id}")
            return {
                "success": True,
                "adapter_id": adapter_id,
                "adapter_type": instance.adapter_type,
                "services_unregistered": len(instance.services_registered),
                "was_running": True
            }
            
        except Exception as e:
            logger.error(f"Failed to unload adapter {adapter_id}: {e}", exc_info=True)
            return {
                "success": False,
                "adapter_id": adapter_id,
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
                    "adapter_id": adapter_id,
                    "error": f"Adapter with ID '{adapter_id}' not found"
                }
            
            instance = self.loaded_adapters[adapter_id]
            adapter_type = instance.adapter_type
            
            logger.info(f"Reloading adapter {adapter_id} with new config")
            
            unload_result = await self.unload_adapter(adapter_id)
            if not unload_result["success"]:
                return unload_result
            
            load_result = await self.load_adapter(adapter_type, adapter_id, config_params)
            
            if load_result["success"]:
                logger.info(f"Successfully reloaded adapter {adapter_id}")
            
            return load_result
            
        except Exception as e:
            logger.error(f"Failed to reload adapter {adapter_id}: {e}", exc_info=True)
            return {
                "success": False,
                "adapter_id": adapter_id,
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
                    "adapter_type": instance.adapter_type,
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
        if adapter_id not in self.loaded_adapters:
            return {
                "success": False,
                "found": False,
                "error": f"Adapter with ID '{adapter_id}' not found"
            }
        
        try:
            instance = self.loaded_adapters[adapter_id]
            
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
                "success": True,
                "found": True,
                "adapter_id": adapter_id,
                "adapter_type": instance.adapter_type,
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
                "success": False,
                "found": False,
                "error": str(e)
            }
    
    async def load_adapter_from_template(self, template_name: str, adapter_id: Optional[str] = None) -> Dict[str, Any]:
        """Load adapter configuration from an agent template
        
        Args:
            template_name: Name of the agent template to load
            adapter_id: Optional unique ID for the adapter
            
        Returns:
            Dict with load results
        """
        try:
            from pathlib import Path
            import yaml
            
            template_overlay_path = Path("ciris_templates") / f"{template_name}.yaml"
            adapter_types = []
            
            if template_overlay_path.exists():
                try:
                    with open(template_overlay_path, 'r') as f:
                        template_data = yaml.safe_load(f) or {}
                    
                    if 'discord_config' in template_data or template_data.get('discord_config'):
                        adapter_types.append('discord')
                    if 'api_config' in template_data or template_data.get('api_config'):
                        adapter_types.append('api')
                    if 'cli_config' in template_data or template_data.get('cli_config'):
                        adapter_types.append('cli')
                except Exception:
                    adapter_types = ['discord', 'api', 'cli']
            
            config = await ConfigLoader.load_config(template_name=template_name)
            
            if not config.agent_templates or template_name not in config.agent_templates:
                return {
                    "success": False,
                    "error": f"Template '{template_name}' not found in configuration"
                }
            
            template = config.agent_templates[template_name]
            results = []
            
            if template.discord_config:
                discord_params = {
                    "channel_id": template.discord_config.home_channel_id,
                    "bot_token": template.discord_config.bot_token
                }
                result = await self.load_adapter("discord", adapter_id or f"discord_{template_name}", discord_params)
                results.append({"adapter_type": "discord", **result})
            
            if template.api_config:
                api_params = {
                    "host": template.api_config.host,
                    "port": template.api_config.port
                }
                result = await self.load_adapter("api", adapter_id or f"api_{template_name}", api_params)
                results.append({"adapter_type": "api", **result})
            
            if template.cli_config:
                cli_params: Dict[str, Any] = {}
                result = await self.load_adapter("cli", adapter_id or f"cli_{template_name}", cli_params)
                results.append({"adapter_type": "cli", **result})
            
            success_count = sum(1 for r in results if r.get("success", False))
            
            return {
                "success": success_count > 0,
                "template_name": template_name,
                "adapters_loaded": success_count,
                "total_attempted": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Failed to load adapters from template {template_name}: {e}", exc_info=True)
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
                    logger.error(f"Adapter {instance.adapter.__class__.__name__} provided invalid ServiceRegistration: {reg}")  # type: ignore[unreachable]
                    continue
                
                service_key = f"{reg.service_type.value}:{reg.provider.__class__.__name__}"
                
                if reg.handlers:  # Register for specific handlers
                    for handler_name in reg.handlers:
                        self.runtime.service_registry.register(
                            handler=handler_name,
                            service_type=reg.service_type,  # Pass ServiceType enum, not .value
                            provider=reg.provider,
                            priority=reg.priority,
                            capabilities=reg.capabilities,
                            priority_group=reg.priority_group,
                            strategy=reg.strategy
                        )
                        instance.services_registered.append(f"{handler_name}:{service_key}")
                else:  # Register globally
                    self.runtime.service_registry.register_global(
                        service_type=reg.service_type,  # Pass ServiceType enum, not .value
                        provider=reg.provider,
                        priority=reg.priority,
                        capabilities=reg.capabilities,
                        priority_group=reg.priority_group,
                        strategy=reg.strategy
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
            
            for service_key in instance.services_registered:
                logger.info(f"Would unregister service: {service_key} from adapter {instance.adapter_id}")
            
            instance.services_registered.clear()
            
        except Exception as e:
            logger.error(f"Error unregistering services for adapter {instance.adapter_id}: {e}", exc_info=True)

    async def get_adapter_info(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific adapter."""
        if adapter_id not in self.loaded_adapters:
            return {}
        
        try:
            instance = self.loaded_adapters[adapter_id]
            
            return {
                "adapter_id": adapter_id,
                "adapter_type": instance.adapter_type,
                "config": instance.config_params,
                "load_time": instance.loaded_at.isoformat(),
                "is_running": instance.is_running
            }
            
        except Exception as e:
            logger.error(f"Failed to get adapter info for {adapter_id}: {e}", exc_info=True)
            return {}

    def get_communication_adapter_status(self) -> Dict[str, Any]:
        """Get status of communication adapters."""
        communication_adapter_types = {"discord", "api", "cli"}  # Known communication adapter types
        
        communication_adapters = []
        running_count = 0
        
        for adapter_id, instance in self.loaded_adapters.items():
            if instance.adapter_type in communication_adapter_types:
                communication_adapters.append({
                    "adapter_id": adapter_id,
                    "adapter_type": instance.adapter_type,
                    "is_running": instance.is_running
                })
                if instance.is_running:
                    running_count += 1
        
        total_count = len(communication_adapters)
        safe_to_unload = total_count > 1  # Safe if more than one communication adapter
        
        warning_message = None
        if total_count == 1:
            warning_message = "Only one communication adapter remaining. Unloading it will disable communication."
        elif total_count == 0:
            warning_message = "No communication adapters are loaded."
        
        return {
            "total_communication_adapters": total_count,
            "running_communication_adapters": running_count,
            "communication_adapters": communication_adapters,
            "safe_to_unload": safe_to_unload,
            "warning_message": warning_message
        }
