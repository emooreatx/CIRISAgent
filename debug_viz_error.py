#!/usr/bin/env python3
"""Debug visualization endpoint error."""

import requests
import json

# Login
response = requests.post('http://localhost:8080/v1/auth/login', 
    json={'username': 'admin', 'password': 'ciris_admin_password'})
token = response.json()['access_token']

# Get visualization with error details
headers = {'Authorization': f'Bearer {token}'}
response = requests.get('http://localhost:8080/v1/memory/visualize/graph',
    headers=headers,
    params={
        'scope': 'LOCAL',
        'node_type': 'concept',
        'layout': 'force',
        'width': 1200,
        'height': 600,
        'limit': 100
    })

print(f'Status: {response.status_code}')
if response.status_code != 200:
    print('Error:', response.text)
    print('\nTrying without node_type parameter...')
    
    # Try without node_type
    response2 = requests.get('http://localhost:8080/v1/memory/visualize/graph',
        headers=headers,
        params={
            'scope': 'LOCAL',
            'layout': 'force',
            'width': 1200,
            'height': 600,
            'limit': 100
        })
    
    print(f'Status without node_type: {response2.status_code}')
    if response2.status_code == 200:
        print('Success! The issue is with the node_type parameter.')
        print(f'SVG length: {len(response2.text)} bytes')
    else:
        print('Error:', response2.text)