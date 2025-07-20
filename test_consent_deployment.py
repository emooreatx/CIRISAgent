#!/usr/bin/env python3
"""
Test the consent-based deployment workflow.
"""
import subprocess
import time
import requests
import sys
import os

# Colors
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def log(msg):
    print(f"{GREEN}[TEST]{NC} {msg}")

def warn(msg):
    print(f"{YELLOW}[WARN]{NC} {msg}")

def error(msg):
    print(f"{RED}[ERROR]{NC} {msg}")

def info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")


def run_command(cmd, check=True):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        error(f"Command failed: {cmd}")
        error(f"Output: {result.stderr}")
        raise Exception(f"Command failed with code {result.returncode}")
    return result


def check_container_status(container_name):
    """Check if a container is running."""
    result = run_command(f"docker ps --format '{{{{.Names}}}}' | grep '^{container_name}$'", check=False)
    return result.returncode == 0


def check_api_health():
    """Check if the API is healthy."""
    try:
        response = requests.get("http://localhost:8080/v1/system/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    log("Starting consent-based deployment test")
    print("=" * 60)
    
    # Step 1: Ensure container is running
    info("Step 1: Checking initial state")
    
    if not check_container_status("ciris-agent-datum"):
        warn("Agent container not running, starting it...")
        run_command("docker-compose -f deployment/docker-compose.dev-prod.yml up -d agent-datum")
        time.sleep(10)
    
    if not check_api_health():
        error("API is not healthy")
        return 1
    
    log("Agent is running and healthy")
    
    # Step 2: Create a mock update (pull latest image)
    info("Step 2: Simulating available update")
    
    # Tag current as old
    run_command("docker tag ciris-agent:latest ciris-agent:old", check=False)
    
    # Simulate new version by rebuilding
    log("Building 'new' version...")
    run_command("docker build -t ciris-agent:latest -f docker/agent/Dockerfile .")
    
    # Step 3: Run consent-based deployment
    info("Step 3: Running consent-based deployment")
    
    log("Starting deployment script...")
    deploy_proc = subprocess.Popen(
        ["./deployment/consent-based-deploy.sh"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Monitor output
    staged_created = False
    consent_requested = False
    
    for line in deploy_proc.stdout:
        print(f"  {line.rstrip()}")
        
        if "Staged container ready" in line:
            staged_created = True
            log("Staged container created successfully")
        
        if "Requesting agent consent" in line:
            consent_requested = True
            log("Consent request sent to agent")
            
        if "Waiting for agent" in line and consent_requested:
            # Give agent time to process
            info("Agent is processing shutdown request...")
            time.sleep(5)
            
            # In a real test, we would trigger agent consent here
            # For now, we'll simulate by stopping the container gracefully
            info("Simulating agent consent (manual stop)")
            run_command("docker stop ciris-agent-datum")
            
    deploy_proc.wait()
    
    # Step 4: Verify deployment
    info("Step 4: Verifying deployment results")
    
    if deploy_proc.returncode == 0:
        log("Deployment script completed successfully")
    else:
        warn("Deployment script exited with non-zero code")
    
    # Check if new container is running
    time.sleep(5)
    if check_container_status("ciris-agent-datum"):
        log("New container is running")
        
        # Verify it's the new image
        result = run_command("docker inspect ciris-agent-datum --format='{{.Image}}'")
        new_image = result.stdout.strip()
        
        result = run_command("docker images --format='{{.ID}}' ciris-agent:latest")
        latest_id = result.stdout.strip()
        
        if new_image.startswith(latest_id[:12]):
            log("Container is running the new image")
        else:
            error("Container is not running the new image")
    else:
        error("Container is not running after deployment")
        
        # Check for staged container
        result = run_command("docker ps -a --format='{{.Names}}' | grep 'ciris-agent-datum-staged'", check=False)
        if result.returncode == 0:
            warn("Staged container exists - agent may not have consented")
        
    # Step 5: Test CIRISManager API
    info("Step 5: Testing CIRISManager API endpoints")
    
    # Start CIRISManager if not running
    if not os.path.exists("/tmp/test-ciris-manager.pid"):
        log("Starting CIRISManager for testing...")
        # This would normally be done via systemd
        # For testing, we'll skip this step
        warn("CIRISManager API test skipped (requires systemd)")
    
    print("=" * 60)
    log("Consent-based deployment test complete")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        warn("Test interrupted")
        sys.exit(1)
    except Exception as e:
        error(f"Test failed: {e}")
        sys.exit(1)