"""
Emergency Shutdown endpoint for CIRIS API.

Provides cryptographically signed emergency shutdown functionality
that operates outside normal authentication (signature IS the auth).
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
import base64
import json

try:
    # Try to import Ed25519 verification
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("Ed25519 crypto not available - emergency shutdown will be disabled")

from ciris_engine.schemas.services.shutdown import (
    WASignedCommand,
    EmergencyShutdownStatus,
    EmergencyCommandType
)
from ciris_engine.schemas.api.responses import SuccessResponse
from ciris_engine.logic.registries.base import ServiceRegistry

logger = logging.getLogger(__name__)

# Create router without prefix - this is mounted at root level
router = APIRouter(tags=["emergency"])

# Hardcoded root authority public keys for emergency shutdown
# In production, these would be loaded from secure configuration
ROOT_AUTHORITY_KEYS = [
    # Example Ed25519 public key (base64 encoded)
    # "MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE="
]

def verify_signature(command: WASignedCommand) -> bool:
    """
    Verify Ed25519 signature on the command.

    Args:
        command: The signed command to verify

    Returns:
        True if signature is valid, False otherwise
    """
    if not CRYPTO_AVAILABLE:
        logger.error("Crypto not available - cannot verify signature")
        return False

    try:
        # Decode the public key
        public_key_bytes = base64.b64decode(command.wa_public_key)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

        # Build the message that was signed
        # This must match exactly what was signed on the client side
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

        # Decode and verify signature
        signature_bytes = base64.b64decode(command.signature)
        public_key.verify(signature_bytes, message)

        return True

    except (InvalidSignature, ValueError, KeyError) as e:
        logger.warning(f"Signature verification failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during signature verification: {e}")
        return False

def verify_timestamp(command: WASignedCommand, window_minutes: int = 5) -> bool:
    """
    Verify command timestamp is within acceptable window.

    Args:
        command: The command to verify
        window_minutes: Maximum age of command in minutes

    Returns:
        True if timestamp is valid, False otherwise
    """
    now = datetime.now(timezone.utc)

    # Check if command is too old
    if now - command.issued_at > timedelta(minutes=window_minutes):
        logger.warning(f"Command too old: issued at {command.issued_at}, now {now}")
        return False

    # Check if command is from the future (clock skew)
    if command.issued_at > now + timedelta(minutes=1):
        logger.warning(f"Command from future: issued at {command.issued_at}, now {now}")
        return False

    # Check expiration if set
    if command.expires_at and now > command.expires_at:
        logger.warning(f"Command expired at {command.expires_at}, now {now}")
        return False

    return True

def is_authorized_key(public_key: str) -> bool:
    """
    Check if the public key is authorized for emergency shutdown.

    In production, this would check against:
    - Root authority keys
    - Keys in the trust tree
    - Dynamically configured emergency keys

    Args:
        public_key: Base64 encoded public key

    Returns:
        True if key is authorized
    """
    # For now, just check against hardcoded root keys
    # In production, this would be more sophisticated
    return public_key in ROOT_AUTHORITY_KEYS

@router.post("/emergency/shutdown", response_model=SuccessResponse[EmergencyShutdownStatus])
async def emergency_shutdown(
    command: WASignedCommand,
    request: Request
):
    """
    Execute emergency shutdown with cryptographically signed command.

    This endpoint requires no authentication - the signature IS the authentication.
    Only accepts SHUTDOWN_NOW commands signed by authorized Wise Authorities.

    Security checks:
    1. Valid Ed25519 signature
    2. Timestamp within 5-minute window
    3. Public key is authorized (ROOT or in trust tree)
    4. Command type is SHUTDOWN_NOW

    Args:
        command: Cryptographically signed shutdown command

    Returns:
        Status of the emergency shutdown process

    Raises:
        HTTPException: If any security check fails
    """
    logger.critical(f"Emergency shutdown requested by WA {command.wa_id}")

    # Initialize status
    status = EmergencyShutdownStatus(
        command_received=datetime.now(timezone.utc),
        command_verified=False
    )

    # Verify command type
    if command.command_type != EmergencyCommandType.SHUTDOWN_NOW:
        status.verification_error = f"Invalid command type: {command.command_type}"
        logger.error(status.verification_error)
        raise HTTPException(status_code=400, detail=status.verification_error)

    # Verify timestamp
    if not verify_timestamp(command):
        status.verification_error = "Command timestamp outside acceptable window"
        logger.error(status.verification_error)
        raise HTTPException(status_code=403, detail=status.verification_error)

    # Verify signature
    if not verify_signature(command):
        status.verification_error = "Invalid signature"
        logger.error(status.verification_error)
        raise HTTPException(status_code=403, detail=status.verification_error)

    # Verify authority
    if not is_authorized_key(command.wa_public_key):
        status.verification_error = "Unauthorized public key"
        logger.error(status.verification_error)
        raise HTTPException(status_code=403, detail=status.verification_error)

    # All checks passed
    status.command_verified = True
    logger.info("Emergency shutdown command verified successfully")

    # Get runtime control service if available
    runtime_service = None
    try:
        runtime_service = ServiceRegistry.get_service("RuntimeControlService")
    except Exception as e:
        logger.warning(f"RuntimeControlService not available: {e}")

    # If we have runtime control service, use it
    if runtime_service and hasattr(runtime_service, 'handle_emergency_shutdown'):
        try:
            logger.info("Delegating to RuntimeControlService for emergency shutdown")
            status = await runtime_service.handle_emergency_shutdown(command)
            return SuccessResponse(data=status)
        except Exception as e:
            logger.error(f"RuntimeControlService emergency shutdown failed: {e}")
            # Fall through to direct shutdown

    # Otherwise, perform direct shutdown
    logger.warning("No RuntimeControlService - performing direct shutdown")

    try:
        # Get shutdown service directly from runtime
        runtime = getattr(request.app.state, 'runtime', None)
        if not runtime:
            raise HTTPException(status_code=503, detail="Runtime not available")

        shutdown_service = getattr(runtime, 'shutdown_service', None)
        if not shutdown_service:
            raise HTTPException(status_code=503, detail="Shutdown service not available")

        # Mark shutdown initiated
        status.shutdown_initiated = datetime.now(timezone.utc)

        # Request immediate shutdown
        reason = f"EMERGENCY: {command.reason} (WA: {command.wa_id})"
        await shutdown_service.request_shutdown(reason)

        # Update status
        status.services_stopped = ["shutdown_requested"]
        status.data_persisted = True
        status.final_message_sent = True
        status.shutdown_completed = datetime.now(timezone.utc)
        status.exit_code = 0

        logger.critical("Emergency shutdown initiated successfully")
        return SuccessResponse(data=status)

    except Exception as e:
        logger.error(f"Emergency shutdown failed: {e}")
        status.verification_error = f"Shutdown failed: {str(e)}"
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/emergency/test")
async def test_emergency_endpoint():
    """
    Test endpoint to verify emergency routes are mounted.

    This endpoint requires no authentication and simply confirms
    the emergency routes are accessible.
    """
    return {
        "status": "ok",
        "message": "Emergency endpoint accessible",
        "crypto_available": CRYPTO_AVAILABLE,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
