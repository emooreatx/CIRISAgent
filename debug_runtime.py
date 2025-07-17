#!/usr/bin/env python3
import requests
import json

# Login
resp = requests.post('http://localhost:8080/v1/auth/login', json={'username': 'admin', 'password': 'ciris_admin_password'})
token = resp.json()['access_token']

# Get raw service health from runtime control - we need to look at internal APIs
# This is a hack to understand the data structure
headers = {'Authorization': f'Bearer {token}'}

# Try to get the raw health status
print("Checking service health internals...")

# Let's check what endpoints are available
resp = requests.get('http://localhost:8080/openapi.json', headers=headers)
endpoints = [path for path in resp.json()['paths'].keys() if 'system' in path or 'service' in path]
print("\nSystem/Service endpoints:")
for endpoint in sorted(endpoints):
    print(f"  {endpoint}")

# Now let's check the service health directly
resp = requests.get('http://localhost:8080/v1/system/services', headers=headers)
data = resp.json()

# Group services by type
service_groups = {}
for service in data['data']['services']:
    stype = service['type']
    if stype not in service_groups:
        service_groups[stype] = []
    service_groups[stype].append(service['name'])

print("\nServices grouped by type:")
for stype, names in sorted(service_groups.items()):
    print(f"\n{stype}:")
    for name in sorted(names):
        print(f"  - {name}")