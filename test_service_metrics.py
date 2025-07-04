#!/usr/bin/env python3
"""Test script to verify service metrics are reporting correctly."""

import asyncio
import logging
from datetime import datetime, timezone
from ciris_engine.logic.runtime.service_initializer import ServiceInitializer
from ciris_engine.logic.config import get_sqlite_db_full_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_service_metrics():
    """Test that all services report proper metrics."""
    # Initialize services
    initializer = ServiceInitializer()
    registry = await initializer.initialize_all_services(mock_llm=True)
    
    print("\n=== Service Metrics Test ===\n")
    
    # Services to check
    services_to_check = [
        ("ShutdownService", "registered_handlers"),
        ("TSDBConsolidationService", "last_consolidation_timestamp"),
        ("GraphConfigService", "total_configs"),
        ("MemoryService", "db_path_length")  # This should no longer exist
    ]
    
    issues_found = []
    
    for service_name, metric_name in services_to_check:
        service = registry.get_service(service_name)
        if not service:
            print(f"❌ {service_name}: Service not found")
            issues_found.append(f"{service_name} not found")
            continue
            
        status = service.get_status()
        
        # Check if the problematic metric still exists
        if service_name == "MemoryService" and metric_name == "db_path_length":
            if metric_name in status.metrics:
                print(f"❌ {service_name}: Still has db_path_length metric")
                issues_found.append(f"{service_name} still has db_path_length")
            else:
                print(f"✅ {service_name}: db_path_length metric removed")
            continue
        
        # Check other metrics
        if metric_name in status.metrics:
            value = status.metrics[metric_name]
            if service_name == "TSDBConsolidationService" and metric_name == "last_consolidation_timestamp":
                # Should be 0 initially (not yet run) or a timestamp
                if value == 0.0:
                    print(f"✅ {service_name}.{metric_name}: {value} (not yet run)")
                else:
                    # Convert timestamp to readable format
                    dt = datetime.fromtimestamp(value, tz=timezone.utc)
                    print(f"✅ {service_name}.{metric_name}: {value} ({dt})")
            else:
                print(f"✅ {service_name}.{metric_name}: {value}")
        else:
            print(f"❌ {service_name}: Missing metric {metric_name}")
            issues_found.append(f"{service_name} missing {metric_name}")
    
    # Also check all services for general health
    print("\n=== All Service Status ===\n")
    all_services = registry.get_all_services()
    for service in all_services:
        status = service.get_status()
        print(f"{status.service_name}:")
        print(f"  - Healthy: {status.is_healthy}")
        print(f"  - Uptime: {status.uptime_seconds:.1f}s")
        print(f"  - Metrics: {list(status.metrics.keys())}")
    
    # Stop services
    await initializer.stop_all_services()
    
    # Report results
    print("\n=== Test Results ===\n")
    if issues_found:
        print(f"❌ Issues found: {len(issues_found)}")
        for issue in issues_found:
            print(f"  - {issue}")
        return False
    else:
        print("✅ All service metrics are reporting correctly!")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_service_metrics())
    exit(0 if success else 1)