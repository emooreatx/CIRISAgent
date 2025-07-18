#!/usr/bin/env python3
import requests
import json

# Login
resp = requests.post('http://localhost:8080/v1/auth/login', json={'username': 'admin', 'password': 'ciris_admin_password'})
token = resp.json()['access_token']

# Get raw service health from runtime control
headers = {'Authorization': f'Bearer {token}'}

# First, let's get the raw service details from the system
resp = requests.get('http://localhost:8080/v1/system/services', headers=headers)
data = resp.json()

print("Raw service data sample:")
# Find examples of registry services
registry_services = []
for service in data['data']['services']:
    if service['type'] == 'unknown':  # These are typically registry services
        registry_services.append(service['name'])

print(f"\nFound {len(registry_services)} registry services")
print("Names:", sorted(set(registry_services)))

# Now let's check what the runtime control service sees
# We need to check the extended endpoints if they exist
print("\n\nChecking extended system endpoints...")
resp = requests.get('http://localhost:8080/v1/system/services/health', headers=headers)
if resp.status_code == 200:
    health_data = resp.json()
    print("Service health endpoint available!")
    # Look for service details
    if 'data' in health_data and 'service_details' in health_data['data']:
        print("\nService details keys:")
        for key in list(health_data['data']['service_details'].keys())[:10]:
            print(f"  {key}")
else:
    print(f"Service health endpoint not available: {resp.status_code}")

# Try to get adapter info
print("\n\nChecking adapter info...")
resp = requests.get('http://localhost:8080/v1/system/adapters', headers=headers)
if resp.status_code == 200:
    adapters = resp.json()
    print(f"Found {adapters['data']['total_count']} adapters")
    for adapter in adapters['data']['adapters']:
        print(f"\nAdapter: {adapter['adapter_type']} (ID: {adapter['adapter_id']})")
        print(f"  Running: {adapter['is_running']}")
        if adapter.get('tools'):
            print(f"  Tools: {len(adapter['tools'])} available")