#!/usr/bin/env python3
"""Test memory visualization endpoint."""

import requests
import time
from datetime import datetime, timezone
import webbrowser
import tempfile
import os

# Configuration
API_URL = "http://localhost:8080/v1"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"

def login():
    """Login and get auth token."""
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def test_force_layout(token):
    """Test force-directed layout visualization."""
    print("\n=== Testing Force Layout ===")
    
    response = requests.get(
        f"{API_URL}/memory/visualize/graph",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "layout": "force",
            "limit": 30,
            "width": 1200,
            "height": 800
        }
    )
    
    if response.status_code == 200:
        # Save SVG to temp file and open in browser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        print(f"✓ Force layout visualization generated")
        print(f"  Saved to: {temp_path}")
        webbrowser.open(f"file://{temp_path}")
        return temp_path
    else:
        print(f"✗ Force layout failed: {response.status_code} - {response.text}")
        return None

def test_timeline_layout(token):
    """Test timeline layout visualization."""
    print("\n=== Testing Timeline Layout ===")
    
    response = requests.get(
        f"{API_URL}/memory/visualize/graph",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "layout": "timeline",
            "hours": 24,
            "limit": 50,
            "width": 1600,
            "height": 800
        }
    )
    
    if response.status_code == 200:
        # Save SVG to temp file and open in browser
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        print(f"✓ Timeline layout visualization generated")
        print(f"  Saved to: {temp_path}")
        webbrowser.open(f"file://{temp_path}")
        return temp_path
    else:
        print(f"✗ Timeline layout failed: {response.status_code} - {response.text}")
        return None

def test_filtered_visualization(token):
    """Test visualization with type filter."""
    print("\n=== Testing Filtered Visualization ===")
    
    response = requests.get(
        f"{API_URL}/memory/visualize/graph",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "node_type": "concept",
            "layout": "force",
            "limit": 20,
            "width": 1000,
            "height": 1000
        }
    )
    
    if response.status_code == 200:
        # Save SVG to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        print(f"✓ Filtered visualization (concepts only) generated")
        print(f"  Saved to: {temp_path}")
        
        # Check if SVG contains expected elements
        if 'circle' in response.text and 'concept' in response.text:
            print("  ✓ SVG contains node elements")
        if 'Node Types:' in response.text:
            print("  ✓ SVG contains legend")
            
        return temp_path
    else:
        print(f"✗ Filtered visualization failed: {response.status_code} - {response.text}")
        return None

def test_hierarchical_layout(token):
    """Test hierarchical layout visualization."""
    print("\n=== Testing Hierarchical Layout ===")
    
    response = requests.get(
        f"{API_URL}/memory/visualize/graph",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "layout": "hierarchical",
            "limit": 25,
            "width": 1200,
            "height": 900
        }
    )
    
    if response.status_code == 200:
        # Save SVG to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        print(f"✓ Hierarchical layout visualization generated")
        print(f"  Saved to: {temp_path}")
        return temp_path
    else:
        print(f"✗ Hierarchical layout failed: {response.status_code} - {response.text}")
        return None

def test_timeline_with_type(token):
    """Test timeline layout with type filter."""
    print("\n=== Testing Timeline with Type Filter ===")
    
    response = requests.get(
        f"{API_URL}/memory/visualize/graph",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "layout": "timeline",
            "hours": 48,
            "node_type": "observation",
            "limit": 30,
            "width": 1400,
            "height": 600
        }
    )
    
    if response.status_code == 200:
        # Save SVG to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(response.text)
            temp_path = f.name
        
        print(f"✓ Timeline with observation filter generated")
        print(f"  Saved to: {temp_path}")
        
        # Check for timeline elements
        if 'Memory Timeline' in response.text:
            print("  ✓ Timeline title present")
        if response.text.count('<text') > 5:  # Should have time labels
            print("  ✓ Time labels present")
            
        return temp_path
    else:
        print(f"✗ Timeline with filter failed: {response.status_code} - {response.text}")
        return None

def main():
    """Run visualization tests."""
    print("Memory Visualization Test Suite")
    print("=" * 50)
    
    # Login
    print("Logging in...")
    token = login()
    print(f"✓ Login successful")
    
    # Store generated files
    generated_files = []
    
    # Run tests
    files = [
        test_force_layout(token),
        test_timeline_layout(token),
        test_filtered_visualization(token),
        test_hierarchical_layout(token),
        test_timeline_with_type(token)
    ]
    
    generated_files = [f for f in files if f is not None]
    
    print("\n" + "=" * 50)
    print("Test suite completed!")
    print(f"\nGenerated {len(generated_files)} visualization files:")
    for f in generated_files:
        print(f"  - {f}")
    
    print("\nFiles will open in your browser automatically.")
    print("Note: Files are temporary and will be cleaned up on system restart.")

if __name__ == "__main__":
    main()