#!/usr/bin/env python3
"""Test service metrics via API."""

import requests
import json
from datetime import datetime, timezone

def test_service_metrics():
    """Test that all services report proper metrics via API."""
    base_url = "http://localhost:8080"
    
    # Login first
    login_resp = requests.post(
        f"{base_url}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_resp.status_code != 200:
        print(f"❌ Failed to login: {login_resp.status_code}")
        return False
        
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get system health
    health_resp = requests.get(f"{base_url}/v1/system/health", headers=headers)
    
    if health_resp.status_code != 200:
        print(f"❌ Failed to get health: {health_resp.status_code}")
        return False
        
    health_data = health_resp.json()
    
    print("\n=== Service Metrics Test ===\n")
    print(f"Health data keys: {list(health_data.keys())}")
    
    # Pretty print the health data to understand structure
    print(f"Health data: {json.dumps(health_data, indent=2)}")
    
    # Check if services are in a different key
    services_data = health_data.get("services", health_data.get("service_health", []))
    
    # Services to check
    services_to_check = [
        ("ShutdownService", "registered_handlers"),
        ("TSDBConsolidationService", "last_consolidation_timestamp"),
        ("GraphConfigService", "total_configs"),
        ("MemoryService", "db_path_length")  # This should no longer exist
    ]
    
    issues_found = []
    
    # Find services in health data
    for service_name, metric_name in services_to_check:
        service_found = False
        
        for service in services_data:
            if service["name"] == service_name:
                service_found = True
                metrics = service.get("metrics", {})
                
                # Check if the problematic metric still exists
                if service_name == "MemoryService" and metric_name == "db_path_length":
                    if metric_name in metrics:
                        print(f"❌ {service_name}: Still has db_path_length metric (value: {metrics[metric_name]})")
                        issues_found.append(f"{service_name} still has db_path_length")
                    else:
                        print(f"✅ {service_name}: db_path_length metric removed")
                    break
                
                # Check other metrics
                if metric_name in metrics:
                    value = metrics[metric_name]
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
                break
        
        if not service_found:
            print(f"❌ {service_name}: Service not found in health data")
            issues_found.append(f"{service_name} not found")
    
    # Show all services
    print("\n=== All Service Status ===\n")
    for service in services_data:
        print(f"{service['name']}:")
        print(f"  - Healthy: {service['healthy']}")
        print(f"  - Uptime: {service.get('uptime_seconds', 0):.1f}s")
        print(f"  - Metrics: {list(service.get('metrics', {}).keys())}")
    
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
    try:
        success = test_service_metrics()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("❌ Failed to connect to API. Make sure the CIRIS agent is running on port 8080.")
        exit(1)