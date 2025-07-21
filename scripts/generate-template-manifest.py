#!/usr/bin/env python3
"""
Generate a signed manifest of pre-approved CIRIS templates.

This script:
1. Calculates SHA-256 checksums of all pre-approved templates
2. Creates a JSON manifest with template metadata
3. Signs the manifest with the root private key
4. Outputs pre-approved-templates.json
"""

import json
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from nacl.signing import SigningKey
from nacl.encoding import Base64Encoder
import base64

# Pre-approved templates and their descriptions
TEMPLATES = {
    "default": "Datum - baseline agent template",
    "sage": "Sage - wise questioning agent",
    "scout": "Scout - direct action demonstrator",
    "echo-core": "Echo-Core - general community moderation",
    "echo-speculative": "Echo-Speculative - speculative discussion moderation",
    "echo": "Echo - base moderation template"
}

def calculate_file_checksum(filepath):
    """Calculate SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_root_private_key():
    """Load the root private key from ~/.ciris/wa_keys/root_wa.key"""
    key_path = Path.home() / ".ciris" / "wa_keys" / "root_wa.key"
    if not key_path.exists():
        print(f"Error: Root private key not found at {key_path}")
        sys.exit(1)
    
    with open(key_path, "rb") as f:
        key_bytes = f.read()
    
    # The key file contains just the 32-byte private key
    if len(key_bytes) != 32:
        print(f"Error: Invalid key length {len(key_bytes)}, expected 32 bytes")
        sys.exit(1)
    
    return SigningKey(key_bytes)

def main():
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Check templates directory exists
    templates_dir = Path("ciris_templates")
    if not templates_dir.exists():
        print(f"Error: Templates directory not found at {templates_dir}")
        sys.exit(1)
    
    # Calculate checksums
    manifest = {
        "version": "1.0",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "templates": {}
    }
    
    for template_name, description in TEMPLATES.items():
        template_path = templates_dir / f"{template_name}.yaml"
        if not template_path.exists():
            print(f"Warning: Template {template_path} not found, skipping")
            continue
        
        checksum = calculate_file_checksum(template_path)
        manifest["templates"][template_name] = {
            "checksum": f"sha256:{checksum}",
            "description": description
        }
        print(f"✓ {template_name}: {checksum}")
    
    # Sign the templates object
    signing_key = load_root_private_key()
    
    # Create deterministic JSON of templates for signing
    templates_json = json.dumps(manifest["templates"], sort_keys=True, separators=(',', ':'))
    templates_bytes = templates_json.encode('utf-8')
    
    # Sign with Ed25519
    signed = signing_key.sign(templates_bytes)
    signature = base64.b64encode(signed.signature).decode('ascii')
    
    # Add signature to manifest
    manifest["root_signature"] = signature
    
    # Also include the public key for verification
    public_key = signing_key.verify_key
    manifest["root_public_key"] = base64.b64encode(public_key.encode()).decode('ascii')
    
    # Write manifest
    output_path = Path("pre-approved-templates.json")
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✓ Manifest written to {output_path}")
    print(f"✓ Signed with root private key")
    print(f"✓ Public key: {manifest['root_public_key']}")

if __name__ == "__main__":
    main()