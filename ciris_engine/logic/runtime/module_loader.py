"""
Module loader with MOCK safety checks.

Ensures MOCK modules disable corresponding real services and emit warnings.
"""

import json
import logging
import importlib
from pathlib import Path
from typing import Any, Dict, List, Set, Optional

from ciris_engine.schemas.runtime.enums import ServiceType

logger = logging.getLogger(__name__)

class ModuleLoader:
    """Loads modules with MOCK safety enforcement."""
    
    def __init__(self, modules_dir: Optional[Path] = None):
        self.modules_dir = modules_dir or Path("ciris_modular_services")
        self.loaded_modules: Dict[str, Any] = {}
        self.mock_modules: Set[str] = set()
        self.disabled_service_types: Set[ServiceType] = set()
        
    def load_module(self, module_name: str, disable_core: bool = False) -> bool:
        """Load a module by name with safety checks."""
        module_path = self.modules_dir / module_name
        manifest_path = module_path / "manifest.json"
        
        if not manifest_path.exists():
            logger.error(f"Module {module_name} not found at {module_path}")
            return False
            
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
                
            module_info = manifest.get("module", {})
            is_mock = module_info.get("MOCK", False)
            
            if is_mock:
                self._handle_mock_module(module_name, manifest, disable_core)
            else:
                self._handle_real_module(module_name, manifest)
                
            self.loaded_modules[module_name] = manifest
            return True
            
        except Exception as e:
            logger.error(f"Failed to load module {module_name}: {e}")
            return False
    
    def _handle_mock_module(self, module_name: str, manifest: Dict[str, Any], disable_core: bool) -> None:
        """Handle loading of MOCK modules with safety warnings."""
        self.mock_modules.add(module_name)
        
        # Emit LOUD warnings
        logger.warning("=" * 80)
        logger.warning("🚨 MOCK MODULE DETECTED 🚨")
        logger.warning(f"Loading MOCK module: {module_name}")
        logger.warning("THIS IS FOR TESTING ONLY - NOT FOR PRODUCTION")
        logger.warning("=" * 80)
        
        # Determine which service types this mock provides
        services = manifest.get("services", [])
        for service in services:
            service_type = ServiceType[service["type"]]
            self.disabled_service_types.add(service_type)
            
            if disable_core:
                logger.warning(f"⚠️  DISABLING all non-mock {service_type.value} services")
                logger.warning(f"⚠️  ONLY {module_name} will provide {service_type.value} services")
        
        # Log to audit trail
        logger.critical(f"MOCK_MODULE_LOADED: {module_name} - Production services disabled for types: {[st.value for st in self.disabled_service_types]}")
    
    def _handle_real_module(self, module_name: str, manifest: Dict[str, Any]) -> None:
        """Handle loading of real modules."""
        # Check if any mock modules are loaded that would conflict
        services = manifest.get("services", [])
        for service in services:
            service_type = ServiceType[service["type"]]
            if service_type in self.disabled_service_types:
                logger.error(f"❌ CANNOT load real module {module_name}: MOCK module already loaded for {service_type.value}")
                raise RuntimeError(f"MOCK safety violation: Cannot load real {service_type.value} service when mock is active")
        
        logger.info(f"Loading module: {module_name}")
    
    def is_service_type_mocked(self, service_type: ServiceType) -> bool:
        """Check if a service type has been mocked."""
        return service_type in self.disabled_service_types
    
    def get_mock_warnings(self) -> List[str]:
        """Get all mock warnings for display."""
        if not self.mock_modules:
            return []
            
        warnings = [
            "🚨 MOCK MODULES ACTIVE 🚨",
            f"Mock modules loaded: {', '.join(self.mock_modules)}",
            f"Disabled service types: {', '.join(st.value for st in self.disabled_service_types)}",
            "DO NOT USE IN PRODUCTION"
        ]
        return warnings
    
    async def initialize_module_services(self, module_name: str, service_registry: Any) -> List[Any]:
        """Initialize services from a loaded module."""
        if module_name not in self.loaded_modules:
            logger.error(f"Module {module_name} not loaded")
            return []
            
        manifest = self.loaded_modules[module_name]
        initialized_services = []
        
        # Add module directory to path
        import sys
        module_path = self.modules_dir / module_name
        sys.path.insert(0, str(self.modules_dir))
        
        try:
            services = manifest.get("services", [])
            for service_config in services:
                service_type = ServiceType[service_config["type"]]
                
                # Skip if this service type is mocked and this isn't the mock
                is_mock = manifest["module"].get("MOCK", False)
                if not is_mock and self.is_service_type_mocked(service_type):
                    logger.warning(f"Skipping {service_config['class']}: {service_type.value} is mocked")
                    continue
                
                # Load service class
                class_path = service_config["class"]
                parts = class_path.split(".")
                module = importlib.import_module(".".join(parts[:-1]))
                service_class = getattr(module, parts[-1])
                
                # Initialize service
                service = service_class()
                await service.start()
                
                # Register with loud warnings if mock
                metadata: Dict[str, Any] = {"module": module_name}
                if is_mock:
                    metadata["MOCK"] = "true"  # String instead of bool
                    metadata["warning"] = "MOCK SERVICE - NOT FOR PRODUCTION"
                
                from ciris_engine.logic.registries.base import Priority
                priority = Priority[service_config.get("priority", "NORMAL")]
                
                service_registry.register_global(
                    service_type=service_type,
                    provider=service,
                    priority=priority,
                    capabilities=manifest.get("capabilities", []),
                    metadata=metadata
                )
                
                initialized_services.append(service)
                
                if is_mock:
                    logger.warning(f"⚠️  MOCK service registered: {service_class.__name__}")
                else:
                    logger.info(f"Service registered: {service_class.__name__}")
                    
        finally:
            sys.path.pop(0)
            
        return initialized_services