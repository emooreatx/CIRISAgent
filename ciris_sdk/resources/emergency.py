"""
Emergency shutdown resource for CIRIS v1 API (Pre-Beta).

This resource handles the critical emergency shutdown endpoint that bypasses
normal authentication to ensure remote ROOT/AUTHORITY can always execute
emergency shutdown even if the main API auth is compromised or unavailable.
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from enum import Enum
import base64
import json
import uuid

from ..transport import Transport
from ..exceptions import CIRISError

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class EmergencyCommandType(str, Enum):
    """Types of emergency commands."""
    SHUTDOWN_NOW = "SHUTDOWN_NOW"
    FREEZE = "FREEZE"
    SAFE_MODE = "SAFE_MODE"


class WASignedCommand(BaseModel):
    """A command signed by a Wise Authority - matches server schema."""
    command_id: str = Field(..., description="Unique command identifier")
    command_type: EmergencyCommandType = Field(..., description="Type of emergency command")
    
    # WA authority
    wa_id: str = Field(..., description="ID of issuing WA")
    wa_public_key: str = Field(..., description="Public key of issuing WA")
    
    # Command details
    issued_at: datetime = Field(..., description="When command was issued")
    expires_at: Optional[datetime] = Field(None, description="Command expiration")
    reason: str = Field(..., description="Reason for emergency command")
    
    # Targeting
    target_agent_id: Optional[str] = Field(None, description="Specific agent or None for all")
    target_tree_path: Optional[List[str]] = Field(None, description="WA tree path for targeting")
    
    # Signature
    signature: str = Field(..., description="Ed25519 signature of command data")
    
    # Chain of authority
    parent_command_id: Optional[str] = Field(None, description="Parent command if relayed")
    relay_chain: List[str] = Field(default_factory=list, description="WA IDs in relay chain")


class EmergencyShutdownResponse(BaseModel):
    """Response from emergency shutdown."""
    success: bool = Field(..., description="Whether shutdown was initiated")
    message: str = Field(..., description="Status message")


class EmergencyResource:
    """
    Emergency operations for v1 API (Pre-Beta).
    
    **WARNING**: This SDK is for the v1 API which is in pre-beta stage.
    
    **CRITICAL**: The emergency shutdown endpoint bypasses normal authentication
    to ensure remote ROOT/AUTHORITY can always execute emergency shutdown even if
    the main API auth is compromised or unavailable.
    
    Security features:
    - Requires Ed25519 cryptographically signed command
    - Signature must be from ROOT or AUTHORITY key
    - Timestamp must be within 5-minute window
    - Executes immediate shutdown without negotiation
    - Separate from /v1/system/shutdown to avoid auth dependencies
    """
    
    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        if not CRYPTO_AVAILABLE:
            raise CIRISError("cryptography package required for emergency shutdown. Install with: pip install cryptography")
    
    async def shutdown(
        self, 
        reason: str, 
        private_key: Ed25519PrivateKey,
        wa_id: str,
        wa_public_key: str,
        target_agent_id: Optional[str] = None,
        expires_minutes: int = 5
    ) -> EmergencyShutdownResponse:
        """
        Execute emergency shutdown with Ed25519 signed command.
        
        This endpoint bypasses normal authentication and requires a
        cryptographically signed command. The signing key must be from
        a ROOT or AUTHORITY Wise Authority.
        
        Args:
            reason: Reason for emergency shutdown
            private_key: Ed25519 private key for signing
            wa_id: ID of the Wise Authority issuing command
            wa_public_key: Base64-encoded public key of the WA
            target_agent_id: Optional specific agent to shutdown
            expires_minutes: Command expiration in minutes (default 5)
            
        Returns:
            EmergencyShutdownResponse indicating if shutdown was initiated
            
        Raises:
            CIRISError: If crypto not available or request fails
            
        Example:
            # Generate or load Ed25519 key pair
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            response = await client.emergency.shutdown(
                reason="Critical security incident",
                private_key=private_key,
                wa_id="root_authority_001",
                wa_public_key=base64.b64encode(public_key_bytes).decode()
            )
        """
        # Create the command
        now = datetime.now(timezone.utc)
        command = WASignedCommand(
            command_id=str(uuid.uuid4()),
            command_type=EmergencyCommandType.SHUTDOWN_NOW,
            wa_id=wa_id,
            wa_public_key=wa_public_key,
            issued_at=now,
            expires_at=now + timedelta(minutes=expires_minutes),
            reason=reason,
            target_agent_id=target_agent_id,
            signature=""  # Will be filled after signing
        )
        
        # Sign the command
        command.signature = self._sign_command(command, private_key)
        
        # Send to emergency endpoint (note: NOT under /v1/)
        result = await self._transport.request(
            "POST",
            "/emergency/shutdown",
            json=command.dict()
        )
        
        return EmergencyShutdownResponse(**result)
    
    def _sign_command(self, command: WASignedCommand, private_key: Ed25519PrivateKey) -> str:
        """
        Create Ed25519 signature of the command data.
        
        Args:
            command: The command to sign
            private_key: Ed25519 private key
            
        Returns:
            Base64-encoded signature
        """
        # Build the message that will be signed (must match server verification)
        message_data = {
            "command_id": command.command_id,
            "command_type": command.command_type,
            "wa_id": command.wa_id,
            "issued_at": command.issued_at.isoformat(),
            "reason": command.reason,
            "target_agent_id": command.target_agent_id,
        }
        if command.expires_at:
            message_data["expires_at"] = command.expires_at.isoformat()
        if command.target_tree_path:
            message_data["target_tree_path"] = command.target_tree_path
        
        # Create canonical JSON (sorted keys, compact)
        message = json.dumps(message_data, sort_keys=True).encode()
        
        # Sign with Ed25519
        signature_bytes = private_key.sign(message)
        
        # Return base64-encoded signature
        return base64.b64encode(signature_bytes).decode('ascii')
    
    def verify_signature(
        self, 
        command: WASignedCommand,
        public_key_bytes: bytes
    ) -> bool:
        """
        Verify an Ed25519 signature matches the command.
        
        This is useful for testing or verification purposes.
        
        Args:
            command: The command with signature
            public_key_bytes: Raw bytes of Ed25519 public key
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            from cryptography.exceptions import InvalidSignature
            
            # Create public key
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            # Build message (same as _sign_command)
            message_data = {
                "command_id": command.command_id,
                "command_type": command.command_type,
                "wa_id": command.wa_id,
                "issued_at": command.issued_at.isoformat(),
                "reason": command.reason,
                "target_agent_id": command.target_agent_id,
            }
            if command.expires_at:
                message_data["expires_at"] = command.expires_at.isoformat()
            if command.target_tree_path:
                message_data["target_tree_path"] = command.target_tree_path
            
            message = json.dumps(message_data, sort_keys=True).encode()
            
            # Verify signature
            signature_bytes = base64.b64decode(command.signature)
            public_key.verify(signature_bytes, message)
            return True
            
        except (InvalidSignature, ValueError):
            return False
        except Exception:
            return False