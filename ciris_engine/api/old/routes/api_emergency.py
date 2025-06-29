"""
Emergency shutdown endpoint for CIRIS API v2.0.

This endpoint bypasses normal authentication to allow emergency shutdown
with cryptographically signed commands from ROOT or AUTHORITY keys.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, status
from datetime import datetime, timezone
import asyncio
import logging

from ciris_engine.schemas.api.emergency import (
    EmergencyShutdownCommand,
    EmergencyShutdownResponse,
    EmergencyStatus
)
from ciris_engine.api.security.emergency import EmergencyShutdownVerifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emergency", tags=["emergency"])

@router.post(
    "/shutdown",
    response_model=EmergencyShutdownResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Emergency Shutdown",
    description="""
    Emergency shutdown endpoint - NO AUTHENTICATION REQUIRED.

    Accepts cryptographically signed shutdown commands from ROOT or AUTHORITY keys.
    Executes immediate shutdown without negotiation.

    Requirements:
    - Command must be signed with a trusted ROOT or AUTHORITY private key
    - Timestamp must be within 5 minutes (prevents replay attacks)
    - Signature must be valid HMAC-SHA256

    This endpoint is designed for critical situations where normal
    authentication may be compromised or unavailable.
    """
)
async def emergency_shutdown(
    command: EmergencyShutdownCommand,
    request: Request,
    background_tasks: BackgroundTasks
) -> EmergencyShutdownResponse:
    """Execute emergency shutdown with signed command."""

    # Get services from app state
    if not hasattr(request.app.state, 'emergency_verifier'):
        logger.error("Emergency verifier not initialized")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Emergency system not configured"
        )

    verifier: EmergencyShutdownVerifier = request.app.state.emergency_verifier
    audit_service = getattr(request.app.state, 'audit_service', None)
    shutdown_service = getattr(request.app.state, 'shutdown_service', None)

    if not shutdown_service:
        logger.error("Shutdown service not available")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Shutdown service not available"
        )

    # Verify the command signature
    is_valid, authority_id = verifier.verify_command(command)

    # Log the attempt (whether successful or not)
    if audit_service:
        try:
            await audit_service.log_action(
                action="emergency_shutdown_attempt",
                actor=authority_id or "unknown",
                context={
                    "success": is_valid,
                    "reason": command.reason,
                    "timestamp": command.timestamp,
                    "force": command.force,
                    "source_ip": request.client.host if request.client else "unknown"
                }
            )
        except Exception as e:
            logger.error(f"Failed to log emergency shutdown attempt: {e}")

    # Handle invalid signature
    if not is_valid:
        logger.warning(f"Emergency shutdown rejected - invalid signature from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid shutdown command signature"
        )

    # Log successful verification
    logger.critical(f"EMERGENCY SHUTDOWN INITIATED by {authority_id}: {command.reason}")

    # Log the verified shutdown command
    if audit_service:
        try:
            await audit_service.log_action(
                action="emergency_shutdown_initiated",
                actor=authority_id,
                context={
                    "reason": command.reason,
                    "timestamp": command.timestamp,
                    "force": command.force,
                    "command_timestamp": command.timestamp,
                    "execution_timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to log emergency shutdown initiation: {e}")

    # Define shutdown task
    async def execute_shutdown() -> None:
        """Execute the emergency shutdown."""
        try:
            # Give a brief moment for response to be sent
            await asyncio.sleep(0.5)

            # Attempt graceful shutdown with timeout
            timeout = 5 if command.force else 30

            logger.info(f"Starting emergency shutdown with {timeout}s timeout")
            await shutdown_service.emergency_shutdown(
                reason=f"Emergency shutdown by {authority_id}: {command.reason}",
                timeout_seconds=timeout
            )

        except asyncio.TimeoutError:
            logger.error("Graceful shutdown timed out, forcing termination")
            import os
            import signal
            os.kill(os.getpid(), signal.SIGKILL)

        except Exception as e:
            logger.error(f"Error during emergency shutdown: {e}")
            # Force kill if all else fails
            import os
            import signal
            os.kill(os.getpid(), signal.SIGKILL)

    # Schedule shutdown in background
    background_tasks.add_task(execute_shutdown)

    # Return acceptance response
    return EmergencyShutdownResponse(
        status="accepted",
        message=f"Emergency shutdown initiated by {authority_id}",
        authority=authority_id,
        timestamp=datetime.now(timezone.utc),
        shutdown_initiated=True
    )

@router.get(
    "/status",
    response_model=EmergencyStatus,
    summary="Emergency System Status",
    description="Get the current status of the emergency shutdown system."
)
async def get_emergency_status(request: Request) -> EmergencyStatus:
    """Get emergency system status (public endpoint)."""

    # Check if emergency system is configured
    if not hasattr(request.app.state, 'emergency_verifier'):
        return EmergencyStatus(
            emergency_system_ready=False,
            trusted_authorities=0,
            last_emergency_command=None,
            failed_attempts_24h=0
        )

    verifier: EmergencyShutdownVerifier = request.app.state.emergency_verifier

    # Get audit service for statistics
    audit_service = getattr(request.app.state, 'audit_service', None)

    # Count failed attempts in last 24 hours
    failed_attempts = 0
    last_command_time = None

    if audit_service:
        try:
            # Query recent emergency attempts
            # This is a simplified version - actual implementation would query audit logs
            pass
        except Exception as e:
            logger.warning(f"Failed to query emergency attempt statistics: {e}")

    return EmergencyStatus(
        emergency_system_ready=True,
        trusted_authorities=len(verifier.list_authorities()),
        last_emergency_command=last_command_time,
        failed_attempts_24h=failed_attempts
    )

# Initialization helper for app startup
async def initialize_emergency_system(
    config_service: Any,
    audit_service: Any,
    shutdown_service: Any
) -> EmergencyShutdownVerifier:
    """
    Initialize emergency shutdown system.

    Should be called during app startup to configure trusted keys.
    """
    try:
        # Get trusted keys from configuration
        trusted_keys = {}

        # Get ROOT key
        root_key = await config_service.get_config("wa_root_key")
        if root_key:
            trusted_keys["ROOT"] = root_key
            logger.info("Loaded ROOT emergency key")

        # Get AUTHORITY keys
        authority_keys = await config_service.get_config("wa_authority_keys") or {}
        for auth_id, key in authority_keys.items():
            if isinstance(key, str):  # Simple string key
                trusted_keys[auth_id] = key
            elif isinstance(key, dict) and "public_key" in key:  # Structured key
                trusted_keys[auth_id] = key["public_key"]

        logger.info(f"Loaded {len(authority_keys)} AUTHORITY emergency keys")

        # Create verifier
        verifier = EmergencyShutdownVerifier(trusted_keys)

        # Log initialization
        if audit_service:
            await audit_service.log_action(
                action="emergency_system_initialized",
                actor="system",
                context={
                    "trusted_authorities": len(trusted_keys),
                    "authority_ids": list(trusted_keys.keys())
                }
            )

        return verifier

    except Exception as e:
        logger.error(f"Failed to initialize emergency system: {e}")
        # Return empty verifier rather than failing startup
        return EmergencyShutdownVerifier({})
