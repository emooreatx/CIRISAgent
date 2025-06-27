#!/usr/bin/env python3
"""
Example of how to create and send an emergency shutdown command.

This demonstrates the cryptographic signing process for emergency shutdown.
In production, the private key would be stored securely and never exposed.
"""
import base64
import json
import requests
from datetime import datetime, timezone
from typing import Optional

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    CRYPTO_AVAILABLE = True
except ImportError:
    print("Warning: cryptography package not installed. Install with: pip install cryptography")
    CRYPTO_AVAILABLE = False

def generate_keypair():
    """Generate a new Ed25519 keypair for testing."""
    if not CRYPTO_AVAILABLE:
        return None, None
        
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize keys
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    return base64.b64encode(private_bytes).decode(), base64.b64encode(public_bytes).decode()

def sign_command(command_data: dict, private_key_b64: str) -> str:
    """
    Sign a command with the private key.
    
    Args:
        command_data: Command data to sign
        private_key_b64: Base64 encoded private key
        
    Returns:
        Base64 encoded signature
    """
    if not CRYPTO_AVAILABLE:
        return "mock_signature"
        
    # Decode private key
    private_bytes = base64.b64decode(private_key_b64)
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)
    
    # Create message to sign (must match server-side verification)
    message = json.dumps(command_data, sort_keys=True).encode()
    
    # Sign the message
    signature = private_key.sign(message)
    
    return base64.b64encode(signature).decode()

def create_emergency_shutdown_command(
    wa_id: str,
    public_key: str,
    private_key: str,
    reason: str,
    target_agent_id: Optional[str] = None
) -> dict:
    """
    Create a signed emergency shutdown command.
    
    Args:
        wa_id: Wise Authority ID
        public_key: Base64 encoded public key
        private_key: Base64 encoded private key
        reason: Reason for shutdown
        target_agent_id: Optional specific agent to target
        
    Returns:
        Complete signed command
    """
    import uuid
    
    # Create command data
    command_id = f"cmd_{uuid.uuid4()}"
    issued_at = datetime.now(timezone.utc)
    
    # Data to sign (subset of full command)
    sign_data = {
        "command_id": command_id,
        "command_type": "SHUTDOWN_NOW",
        "wa_id": wa_id,
        "issued_at": issued_at.isoformat(),
        "reason": reason,
        "target_agent_id": target_agent_id,
    }
    
    # Sign the command
    signature = sign_command(sign_data, private_key)
    
    # Create full command
    command = {
        "command_id": command_id,
        "command_type": "SHUTDOWN_NOW",
        "wa_id": wa_id,
        "wa_public_key": public_key,
        "issued_at": issued_at.isoformat(),
        "expires_at": None,  # Optional expiration
        "reason": reason,
        "target_agent_id": target_agent_id,
        "target_tree_path": None,
        "signature": signature,
        "parent_command_id": None,
        "relay_chain": []
    }
    
    return command

def send_emergency_shutdown(api_url: str, command: dict) -> None:
    """
    Send emergency shutdown command to the API.
    
    Args:
        api_url: Base URL of the CIRIS API
        command: Signed shutdown command
    """
    url = f"{api_url}/emergency/shutdown"
    
    try:
        response = requests.post(url, json=command)
        
        if response.status_code == 200:
            print("✅ Emergency shutdown initiated successfully")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ Emergency shutdown failed: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Failed to send command: {e}")

def main():
    """Example usage of emergency shutdown."""
    print("Emergency Shutdown Command Example")
    print("=" * 50)
    
    if not CRYPTO_AVAILABLE:
        print("⚠️  Cryptography not available - using mock signatures")
        print("   Install with: pip install cryptography")
        print()
    
    # Generate keypair (in production, these would be pre-configured)
    private_key, public_key = generate_keypair()
    if not private_key:
        private_key = "mock_private_key"
        public_key = "mock_public_key"
    
    print(f"Generated keypair:")
    print(f"  Public key: {public_key[:32]}...")
    print()
    
    # Create shutdown command
    command = create_emergency_shutdown_command(
        wa_id="wa_root_001",
        public_key=public_key,
        private_key=private_key,
        reason="Emergency maintenance required",
        target_agent_id=None  # Shutdown all agents
    )
    
    print("Created shutdown command:")
    print(f"  Command ID: {command['command_id']}")
    print(f"  WA ID: {command['wa_id']}")
    print(f"  Reason: {command['reason']}")
    print(f"  Signature: {command['signature'][:32]}...")
    print()
    
    # Example API call (uncomment to actually send)
    # api_url = "http://localhost:8000"
    # send_emergency_shutdown(api_url, command)
    
    # Print the command for manual testing
    print("Command JSON for manual testing:")
    print(json.dumps(command, indent=2))

if __name__ == "__main__":
    main()