#!/usr/bin/env python3
"""Test API interact endpoint with mock LLM commands on multiple containers."""

import requests
import json
import time
import subprocess
import sys
from datetime import datetime

def test_container(port, container_name):
    """Test a single container."""
    print(f"\n{'='*60}")
    print(f"Testing Container {container_name} (port {port})")
    print(f"{'='*60}")
    
    results = {
        'port': port,
        'container': container_name,
        'login': False,
        'recall': {'success': False, 'response': None, 'time': None},
        'speak': {'success': False, 'response': None, 'time': None},
        'channel_extraction': 'Unknown',
        'errors': []
    }
    
    try:
        # 1. Login
        print(f"\n1. Login to get token...")
        start = time.time()
        login_response = requests.post(
            f"http://localhost:{port}/v1/auth/login",
            json={"username": "admin", "password": "ciris_admin_password"},
            timeout=5
        )
        login_time = time.time() - start
        
        if login_response.status_code == 200:
            token = login_response.json()["access_token"]
            results['login'] = True
            print(f"   ✓ Login successful ({login_time:.2f}s)")
            print(f"   Token: {token[:20]}...")
        else:
            results['errors'].append(f"Login failed: {login_response.status_code}")
            print(f"   ✗ Login failed: {login_response.status_code}")
            return results
            
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Test $recall command
        print(f"\n2. Testing $recall command...")
        start = time.time()
        try:
            recall_response = requests.post(
                f"http://localhost:{port}/v1/agent/interact",
                headers=headers,
                json={"message": "$recall memories"},
                timeout=10
            )
            recall_time = time.time() - start
            
            if recall_response.status_code == 200:
                data = recall_response.json()["data"]
                results['recall']['success'] = True
                results['recall']['response'] = data['response']
                results['recall']['time'] = recall_time
                print(f"   ✓ $recall successful ({recall_time:.2f}s)")
                print(f"   Response: {data['response'][:100]}...")
                print(f"   Processing time: {data['processing_time_ms']}ms")
            else:
                results['errors'].append(f"$recall failed: {recall_response.status_code}")
                print(f"   ✗ $recall failed: {recall_response.status_code}")
        except requests.exceptions.Timeout:
            results['errors'].append("$recall timed out")
            print(f"   ✗ $recall timed out after 10s")
        except Exception as e:
            results['errors'].append(f"$recall error: {str(e)}")
            print(f"   ✗ $recall error: {str(e)}")
            
        # 3. Test $speak command
        print(f"\n3. Testing $speak command...")
        start = time.time()
        try:
            speak_message = f"$speak Hello from container {container_name}"
            speak_response = requests.post(
                f"http://localhost:{port}/v1/agent/interact",
                headers=headers,
                json={"message": speak_message},
                timeout=10
            )
            speak_time = time.time() - start
            
            if speak_response.status_code == 200:
                data = speak_response.json()["data"]
                results['speak']['success'] = True
                results['speak']['response'] = data['response']
                results['speak']['time'] = speak_time
                print(f"   ✓ $speak successful ({speak_time:.2f}s)")
                print(f"   Response: {data['response'][:100]}...")
                print(f"   Processing time: {data['processing_time_ms']}ms")
            else:
                results['errors'].append(f"$speak failed: {speak_response.status_code}")
                print(f"   ✗ $speak failed: {speak_response.status_code}")
        except requests.exceptions.Timeout:
            results['errors'].append("$speak timed out")
            print(f"   ✗ $speak timed out after 10s")
        except Exception as e:
            results['errors'].append(f"$speak error: {str(e)}")
            print(f"   ✗ $speak error: {str(e)}")
            
        # 4. Check container logs for channel extraction
        print(f"\n4. Checking container logs for channel extraction...")
        try:
            # Find the latest log file
            cmd = f"docker exec {container_name} find /app/logs -name 'ciris_agent_*.log' -type f -exec ls -t {{}} + | head -1"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                log_file = result.stdout.strip()
                
                # Check for channel extraction in logs
                cmd = f"docker exec {container_name} tail -200 {log_file} | grep -E 'MOCK_LLM.*channel|Found API channel|Final extracted channel_id' | tail -5"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout:
                    print(f"   Channel extraction logs:")
                    for line in result.stdout.strip().split('\n'):
                        print(f"   > {line}")
                    
                    # Check what channel was extracted
                    if "api_SYSTEM_ADMIN" in result.stdout:
                        results['channel_extraction'] = 'api_SYSTEM_ADMIN'
                    elif "api_admin" in result.stdout:
                        results['channel_extraction'] = 'api_admin'
                    elif "api_0.0.0.0" in result.stdout:
                        results['channel_extraction'] = 'api_0.0.0.0_' + str(port)
                else:
                    print(f"   No channel extraction logs found")
                    
                # Also check for the actual commands in context
                cmd = f"docker exec {container_name} tail -200 {log_file} | grep -E 'user_input:|task:|content:' | grep -E 'recall|speak' | tail -5"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.stdout:
                    print(f"\n   Command context logs:")
                    for line in result.stdout.strip().split('\n'):
                        print(f"   > {line}")
            else:
                print(f"   Could not find log file")
        except Exception as e:
            print(f"   Error checking logs: {str(e)}")
            
    except Exception as e:
        results['errors'].append(f"Unexpected error: {str(e)}")
        print(f"\n✗ Unexpected error: {str(e)}")
        
    return results

def main():
    """Test containers 0-3."""
    containers = [
        (8080, "ciris_mock_llm_container0"),
        (8081, "ciris_mock_llm_container1"),
        (8082, "ciris_mock_llm_container2"),
        (8083, "ciris_mock_llm_container3")
    ]
    
    all_results = []
    
    print(f"Starting API command tests at {datetime.now()}")
    
    for port, container in containers:
        results = test_container(port, container)
        all_results.append(results)
        time.sleep(1)  # Brief pause between containers
        
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    success_count = 0
    for r in all_results:
        status = "✓" if (r['recall']['success'] or r['speak']['success']) else "✗"
        print(f"\nContainer {r['container']} ({r['port']}): {status}")
        print(f"  - Login: {'✓' if r['login'] else '✗'}")
        print(f"  - $recall: {'✓' if r['recall']['success'] else '✗'} ({r['recall']['time']:.2f}s)" if r['recall']['time'] else "  - $recall: ✗")
        print(f"  - $speak: {'✓' if r['speak']['success'] else '✗'} ({r['speak']['time']:.2f}s)" if r['speak']['time'] else "  - $speak: ✗")
        print(f"  - Channel extracted: {r['channel_extraction']}")
        if r['errors']:
            print(f"  - Errors: {', '.join(r['errors'])}")
            
        if r['recall']['success'] or r['speak']['success']:
            success_count += 1
            
        # Check for unexpected responses
        if r['recall']['response'] and "MOCKLLM DISCLAIMER" in r['recall']['response']:
            print(f"  ⚠️  Mock LLM returned generic response for $recall")
        if r['speak']['response'] and "MOCKLLM DISCLAIMER" in r['speak']['response']:
            print(f"  ⚠️  Mock LLM returned generic response for $speak")
            
    print(f"\n{'='*60}")
    print(f"Overall: {success_count}/4 containers responded successfully")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()