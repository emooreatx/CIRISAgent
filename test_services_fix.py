#!/usr/bin/env python3
import requests
import traceback

try:
    # Login 
    resp = requests.post('http://localhost:8080/v1/auth/login', json={'username': 'admin', 'password': 'ciris_admin_password'})
    print(f'Login status: {resp.status_code}')
    if resp.status_code == 200:
        token = resp.json()['access_token']
        print('Got token')
        
        # Try services endpoint
        headers = {'Authorization': f'Bearer {token}'}
        resp = requests.get('http://localhost:8080/v1/system/services', headers=headers, timeout=5)
        print(f'Services endpoint status: {resp.status_code}')
        if resp.status_code != 200:
            print(f'Error response: {resp.text}')
        else:
            data = resp.json()
            print(f'Total services: {data["data"]["total_services"]}')
            
            # Look for services with adapter prefixes
            prefixed = []
            for service in data['data']['services']:
                if '-' in service['name'] and any(prefix in service['name'] for prefix in ['API', 'DISCORD', 'CLI']):
                    prefixed.append(service['name'])
                    
            print(f'\nServices with adapter prefixes: {len(prefixed)}')
            if prefixed:
                print('Examples:', prefixed[:5])
    else:
        print(f'Login failed: {resp.text}')
except Exception as e:
    print(f'Exception: {type(e).__name__}: {e}')
    traceback.print_exc()