"""
Dynamic loader for modular services.

Discovers and loads services from the ciris_modular_services directory.
"""

import json
import logging
import importlib
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ciris_engine.protocols.services import ServiceProtocol
from ciris_engine.schemas.runtime.enums import ServiceType, Priority

logger = logging.getLogger(__name__)

class ModularServiceLoader:
    """Loads modular services from external packages."""
    
    def __init__(self, services_dir: Path = None):
        self.services_dir = services_dir or Path("ciris_modular_services")
        self.loaded_services: Dict[str, Any] = {}
        
    def discover_services(self) -> List[Dict[str, Any]]:
        """Discover all modular services with valid manifests."""
        services = []
        
        if not self.services_dir.exists():
            logger.info(f"Modular services directory not found: {self.services_dir}")
            return services
            
        for service_dir in self.services_dir.iterdir():
            if not service_dir.is_dir() or service_dir.name.startswith("_"):
                continue
                
            manifest_path = service_dir / "manifest.json"
            if manifest_path.exists():
                try:
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                    manifest["path"] = service_dir
                    services.append(manifest)
                    logger.info(f"Discovered modular service: {manifest['service']['name']}")
                except Exception as e:
                    logger.error(f"Failed to load manifest from {service_dir}: {e}")
                    
        return services
    
    def validate_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Validate a service manifest has required fields."""
        required = ["service", "capabilities", "dependencies", "exports"]
        for field in required:
            if field not in manifest:
                logger.error(f"Manifest missing required field: {field}")
                return False
                
        service_info = manifest["service"]
        required_service_fields = ["name", "version", "type"]
        for field in required_service_fields:
            if field not in service_info:
                logger.error(f"Service info missing required field: {field}")
                return False
                
        return True
    
    def check_dependencies(self, manifest: Dict[str, Any]) -> bool:
        """Check if service dependencies are available."""
        deps = manifest.get("dependencies", {})
        
        # Check protocol dependencies
        for protocol in deps.get("protocols", []):
            try:
                parts = protocol.split(".")
                module = importlib.import_module(".".join(parts[:-1]))
                if not hasattr(module, parts[-1]):
                    logger.error(f"Protocol not found: {protocol}")
                    return False
            except ImportError as e:
                logger.error(f"Failed to import protocol {protocol}: {e}")
                return False
                
        # Check schema dependencies
        for schema in deps.get("schemas", []):
            try:
                importlib.import_module(schema)
            except ImportError as e:
                logger.error(f"Failed to import schema {schema}: {e}")
                return False
                
        return True
    
    def load_service(self, manifest: Dict[str, Any]) -> Optional[Type[ServiceProtocol]]:
        """Dynamically load a service class from manifest."""
        if not self.validate_manifest(manifest):
            return None
            
        if not self.check_dependencies(manifest):
            logger.error(f"Dependencies not satisfied for {manifest['service']['name']}")
            return None
            
        service_path = manifest["path"]
        service_name = manifest["service"]["name"]
        
        # Add service directory to Python path temporarily
        import sys
        sys.path.insert(0, str(self.services_dir))
        
        try:
            # Import the service module
            exports = manifest["exports"]
            service_class_path = exports["service_class"]
            parts = service_class_path.split(".")
            
            # Build import path relative to services directory
            module_path = ".".join(parts[:-1])
            class_name = parts[-1]
            
            # Import module
            module = importlib.import_module(module_path)
            service_class = getattr(module, class_name)
            
            logger.info(f"Successfully loaded modular service: {service_name}")
            self.loaded_services[service_name] = {
                "class": service_class,
                "manifest": manifest
            }
            
            return service_class
            
        except Exception as e:
            logger.error(f"Failed to load service {service_name}: {e}")
            return None
        finally:
            # Remove from path
            sys.path.pop(0)
    
    def get_service_metadata(self, service_name: str) -> Dict[str, Any]:
        """Get metadata for a loaded service."""
        if service_name in self.loaded_services:
            return self.loaded_services[service_name]["manifest"]
        return {}
    
    async def initialize_modular_services(self, service_registry: Any, config: Any) -> List[Any]:
        """Initialize all discovered modular services."""
        initialized_services = []
        
        # Discover services
        discovered = self.discover_services()
        
        for manifest in discovered:
            service_info = manifest["service"]
            
            # Skip if production mode and service is test-only
            if not getattr(config, "mock_llm", False) and service_info.get("test_only", False):
                logger.info(f"Skipping test-only service: {service_info['name']}")
                continue
                
            # Load service class
            service_class = self.load_service(manifest)
            if not service_class:
                continue
                
            try:
                # Initialize service
                service_config = manifest.get("configuration", {})
                service_instance = service_class(**service_config)
                await service_instance.start()
                
                # Register with service registry
                service_type = ServiceType[service_info["type"]]
                priority = Priority[service_info.get("priority", "NORMAL")]
                
                service_registry.register_global(
                    service_type=service_type,
                    provider=service_instance,
                    priority=priority,
                    capabilities=manifest["capabilities"],
                    metadata=manifest.get("metadata", {})
                )
                
                initialized_services.append(service_instance)
                logger.info(f"Initialized modular service: {service_info['name']}")
                
            except Exception as e:
                logger.error(f"Failed to initialize {service_info['name']}: {e}")
                
        return initialized_services