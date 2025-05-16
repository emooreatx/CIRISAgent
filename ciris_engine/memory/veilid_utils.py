"""Veilid cryptographic utilities for agent operations."""

import os
import base64
import asyncio
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

async def generate_keypair() -> x25519.X25519PrivateKey:
    """Generate a new X25519 key pair for Veilid communication."""
    private_key = x25519.X25519PrivateKey.generate()
    return private_key

async def register_agent(agent_id: str) -> str:
    """Register an agent in the Veilid DHT and return its public key."""
    private_key = await generate_keypair()
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(public_key).decode('utf-8')