"""
Emergency shutdown security for CIRIS API v2.0.

Provides cryptographic verification of emergency shutdown commands
without requiring normal authentication.
"""
import hashlib
import hmac
import json
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timezone
import logging

from ciris_engine.schemas.api.emergency import EmergencyShutdownCommand

logger = logging.getLogger(__name__)

class EmergencyShutdownVerifier:
    """
    Verify emergency shutdown commands using cryptographic signatures.

    Commands must be:
    1. Signed by a trusted ROOT or AUTHORITY key
    2. Have a timestamp within 5 minutes (prevent replay attacks)
    3. Have a valid HMAC-SHA256 signature
    """

    def __init__(self, trusted_keys: Dict[str, str]):
        """
        Initialize with trusted public keys.

        Args:
            trusted_keys: Map of authority_id -> public_key
        """
        self.trusted_keys = trusted_keys
        self._valid_window_seconds = 300  # 5 minute window

    def verify_command(
        self,
        command: EmergencyShutdownCommand
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify an emergency shutdown command.

        Args:
            command: Emergency shutdown command to verify

        Returns:
            Tuple of (is_valid, authority_id or None)
        """
        try:
            # Step 1: Verify timestamp is recent
            if not self._verify_timestamp(command.timestamp):
                logger.warning(f"Emergency shutdown rejected: timestamp too old ({command.timestamp})")
                return False, None

            # Step 2: Verify signature against all trusted keys
            for authority_id, public_key in self.trusted_keys.items():
                if self._verify_signature(command, public_key):
                    logger.info(f"Emergency shutdown verified from {authority_id}")
                    return True, authority_id

            logger.warning("Emergency shutdown rejected: invalid signature")
            return False, None

        except Exception as e:
            logger.error(f"Error verifying emergency shutdown: {e}")
            return False, None

    def _verify_timestamp(self, timestamp_str: str) -> bool:
        """
        Verify timestamp is within valid window.

        Args:
            timestamp_str: ISO format timestamp

        Returns:
            True if timestamp is valid
        """
        try:
            # Parse timestamp
            command_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

            # Ensure timezone aware
            if command_time.tzinfo is None:
                command_time = command_time.replace(tzinfo=timezone.utc)

            # Check if within window
            now = datetime.now(timezone.utc)
            time_diff = abs((now - command_time).total_seconds())

            return time_diff <= self._valid_window_seconds

        except Exception as e:
            logger.error(f"Error parsing timestamp: {e}")
            return False

    def _verify_signature(
        self,
        command: EmergencyShutdownCommand,
        public_key: str
    ) -> bool:
        """
        Verify command signature with a specific key.

        Args:
            command: Command to verify
            public_key: Public key to verify against

        Returns:
            True if signature is valid
        """
        try:
            # Create canonical message for signing
            # Must match exactly what was signed
            message_dict = {
                "action": command.action,
                "reason": command.reason,
                "timestamp": command.timestamp,
                "force": command.force
            }

            # Ensure consistent JSON serialization
            message = json.dumps(message_dict, sort_keys=True, separators=(',', ':'))

            # Calculate expected signature
            expected_signature = hmac.new(
                public_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # Constant-time comparison to prevent timing attacks
            return hmac.compare_digest(expected_signature, command.signature)

        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False

    def add_trusted_key(self, authority_id: str, public_key: str) -> None:
        """Add a new trusted authority key."""
        self.trusted_keys[authority_id] = public_key
        logger.info(f"Added trusted key for {authority_id}")

    def remove_trusted_key(self, authority_id: str) -> bool:
        """Remove a trusted authority key."""
        if authority_id in self.trusted_keys:
            del self.trusted_keys[authority_id]
            logger.info(f"Removed trusted key for {authority_id}")
            return True
        return False

    def list_authorities(self) -> list[str]:
        """List all trusted authority IDs."""
        return list(self.trusted_keys.keys())

    @staticmethod
    def generate_signature(
        command_dict: Dict[str, Any],
        private_key: str
    ) -> str:
        """
        Generate signature for a command (for testing/tools).

        Args:
            command_dict: Command dictionary with action, reason, timestamp, force
            private_key: Private key for signing

        Returns:
            Hex-encoded signature
        """
        # Create canonical message
        message = json.dumps(command_dict, sort_keys=True, separators=(',', ':'))

        # Generate signature
        signature = hmac.new(
            private_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return signature

def create_signed_command(
    reason: str,
    private_key: str,
    force: bool = True,
    timestamp: Optional[str] = None
) -> EmergencyShutdownCommand:
    """
    Helper to create a properly signed emergency shutdown command.

    Args:
        reason: Reason for shutdown
        private_key: Private key for signing
        force: Whether to force immediate shutdown
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Signed emergency shutdown command
    """
    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    # Create command data
    command_data = {
        "action": "emergency_shutdown",
        "reason": reason,
        "timestamp": timestamp,
        "force": force
    }

    # Generate signature
    signature = EmergencyShutdownVerifier.generate_signature(command_data, private_key)

    # Create command object
    return EmergencyShutdownCommand(
        action=command_data["action"],
        reason=command_data["reason"],
        timestamp=command_data["timestamp"],
        force=command_data["force"],
        signature=signature
    )
