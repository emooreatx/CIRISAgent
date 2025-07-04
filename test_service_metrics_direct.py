#!/usr/bin/env python3
"""Test service metrics directly via API services endpoint."""

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
    
    # Get services status
    services_resp = requests.get(f"{base_url}/v1/system/services", headers=headers)
    
    if services_resp.status_code != 200:
        print(f"❌ Failed to get services: {services_resp.status_code}")
        print(f"Response: {services_resp.text}")
        return False
        
    services_data = services_resp.json()
    
    print("\n=== Service Metrics Test ===\n")
    
    # Services to check (use names as they appear in API)
    services_to_check = [
        ("ShutdownService", "registered_handlers"),
        ("TSDBConsolidation", "last_consolidation_timestamp"),
        ("ConfigService", "total_configs"),
        ("MemoryService", "db_path_length")  # This should no longer exist
    ]
    
    issues_found = []
    
    # Handle nested API response format
    if isinstance(services_data, dict) and "data" in services_data:
        services_list = services_data["data"]["services"]
    elif isinstance(services_data, dict) and "services" in services_data:
        services_list = services_data["services"]
    elif isinstance(services_data, list):
        services_list = services_data
    else:
        print(f"Unexpected services data format: {type(services_data)}")
        print(f"Data: {json.dumps(services_data, indent=2)}")
        return False
    
    # Find services in the list
    for service_name, metric_name in services_to_check:
        service_found = False
        
        for service in services_list:
            # Handle different service data formats
            name = service.get("name") or service.get("service_name")
            if name == service_name:
                service_found = True
                # Look for metrics in custom_metrics field
                custom_metrics = service.get("metrics", {}).get("custom_metrics", {})
                metrics = custom_metrics if custom_metrics else service.get("metrics", {})
                
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
            print(f"❌ {service_name}: Service not found in services data")
            issues_found.append(f"{service_name} not found")
    
    # Show all services
    print("\n=== All Service Status ===\n")
    for service in services_list:
        name = service.get("name") or service.get("service_name")
        print(f"{name}:")
        print(f"  - Healthy: {service.get('is_healthy', service.get('healthy', 'N/A'))}")
        uptime = service.get('uptime_seconds')
        print(f"  - Uptime: {uptime:.1f}s" if uptime is not None else "  - Uptime: N/A")
        custom_metrics = service.get('metrics', {}).get('custom_metrics', {})
        print(f"  - Metrics: {list(custom_metrics.keys()) if custom_metrics else 'None'}")
    
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