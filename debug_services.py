#!/usr/bin/env python3
import requests
import json

# Login
resp = requests.post('http://localhost:8080/v1/auth/login', json={'username': 'admin', 'password': 'ciris_admin_password'})
token = resp.json()['access_token']

# Get services
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('http://localhost:8080/v1/system/services', headers=headers)
data = resp.json()

print("Total services:", len(data['data']['services']))
print("\nRegistry services (TOOL, WISE, COMM):")

# Find registry services
for service in data['data']['services']:
    if service['name'] in ['TOOL', 'WISE', 'COMMUNICATION', 'RUNTIME']:
        print(f"  Name: {service['name']}, Type: {service['type']}")

# Check for services with prefixes
print("\nServices with adapter prefixes:")
for service in data['data']['services']:
    if '-' in service['name'] and any(prefix in service['name'] for prefix in ['DISCORD', 'API', 'CLI']):
        print(f"  Name: {service['name']}, Type: {service['type']}")