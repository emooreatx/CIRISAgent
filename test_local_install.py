#!/usr/bin/env python3
"""
Test CIRISManager local installation and configuration.
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def run_command(cmd, check=True):
    """Run a shell command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result

def test_installation():
    """Test CIRISManager installation process."""
    print("Testing CIRISManager Installation")
    print("="*50)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "test-config.yml"
        
        # Test 1: Package installation
        print("\n1. Testing package installation...")
        result = run_command("pip show ciris-manager", check=False)
        if result.returncode == 0:
            print("✓ Package already installed")
        else:
            # Install using setup_manager.py
            setup_path = Path(__file__).parent / "setup_manager.py"
            if setup_path.exists():
                result = run_command(f"python {setup_path} install --user", check=True)
                print("✓ Package installed successfully")
            else:
                print("✗ setup_manager.py not found")
                return False
        
        # Test 2: Command availability
        print("\n2. Testing command availability...")
        result = run_command("which ciris-manager", check=False)
        if result.returncode == 0:
            print(f"✓ Command found at: {result.stdout.strip()}")
        else:
            print("✗ Command not found - checking Python scripts directory")
            result = run_command("python -m ciris_manager --help", check=True)
            print("✓ Module can be run with python -m")
        
        # Test 3: Config generation
        print("\n3. Testing config generation...")
        result = run_command(f"python -m ciris_manager --generate-config --config {config_file}")
        if config_file.exists():
            print("✓ Config file generated successfully")
            with open(config_file) as f:
                print("  Sample config:")
                for i, line in enumerate(f):
                    if i < 10:  # Show first 10 lines
                        print(f"    {line.rstrip()}")
                    elif i == 10:
                        print("    ...")
                        break
        else:
            print("✗ Config generation failed")
            return False
        
        # Test 4: Config validation
        print("\n4. Testing config validation...")
        result = run_command(f"python -m ciris_manager --validate-config --config {config_file}")
        print("✓ Config validation passed")
        
        # Test 5: Manager initialization (dry run)
        print("\n5. Testing manager initialization...")
        # Create a test docker-compose file
        test_compose = Path(tmpdir) / "docker-compose.yml"
        with open(test_compose, 'w') as f:
            f.write("""version: '3.8'
services:
  test:
    image: hello-world
    container_name: test-container
""")
        
        # Update config to use test compose file
        import yaml
        with open(config_file) as f:
            config = yaml.safe_load(f)
        config['docker']['compose_file'] = str(test_compose)
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        # Try to import and create manager
        sys.path.insert(0, os.getcwd())
        try:
            from ciris_manager.manager import CIRISManager
            from ciris_manager.config.settings import CIRISManagerConfig
            
            config_obj = CIRISManagerConfig.from_file(str(config_file))
            manager = CIRISManager(config_obj)
            print("✓ Manager initialized successfully")
            
            # Get status
            status = manager.get_status()
            print(f"  Manager status: {'running' if status['running'] else 'stopped'}")
            print(f"  Components: {list(status['components'].keys())}")
            
        except Exception as e:
            print(f"✗ Manager initialization failed: {e}")
            return False
    
    print("\n" + "="*50)
    print("All tests passed! ✓")
    return True

def test_systemd_setup():
    """Test systemd service setup (informational only)."""
    print("\n\nSystemd Service Setup Guide")
    print("="*50)
    
    service_file = Path("deployment/ciris-manager.service")
    if service_file.exists():
        print("✓ Service file found at:", service_file)
        print("\nTo install as systemd service (requires sudo):")
        print("  1. sudo cp deployment/ciris-manager.service /etc/systemd/system/")
        print("  2. sudo systemctl daemon-reload")
        print("  3. sudo systemctl enable ciris-manager")
        print("  4. sudo systemctl start ciris-manager")
        print("\nTo check status:")
        print("  sudo systemctl status ciris-manager")
        print("  sudo journalctl -u ciris-manager -f")
    else:
        print("✗ Service file not found")
    
    # Check if installation script exists
    install_script = Path("deployment/install-ciris-manager.sh")
    if install_script.exists():
        print("\n✓ Automated installation script available:")
        print(f"  sudo {install_script}")

def main():
    """Run all tests."""
    print("CIRISManager Local Installation Test")
    print("====================================\n")
    
    # Run installation tests
    if not test_installation():
        print("\nInstallation tests failed!")
        return 1
    
    # Show systemd setup info
    test_systemd_setup()
    
    print("\n✓ CIRISManager is ready for local testing!")
    print("\nNext steps:")
    print("1. Generate a config file: ciris-manager --generate-config")
    print("2. Run manually: ciris-manager --config /path/to/config.yml")
    print("3. Or install as service: sudo ./deployment/install-ciris-manager.sh")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())