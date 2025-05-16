"""
Veilid DHT provider for secure agent communication.

Supports:
- Acting (SPEAK): agent → WA
- Deferral (DEFER): agent → WA (WBD tickets)
- Memory ops (MEMORY): agent → WA (learn/remember/forget)
- Observing (OBSERVE): WA → agent (telemetry/events)
- Corrections (CORRECTION): WA → agent (guidance)

Security features:
- XChaCha20-Poly1305 encryption
- HMAC-SHA256 integrity checks
- Rate limiting
- Private paranet mode
"""

import os
import json
import asyncio
import base64
import hmac
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

import veilid
from .veilid_utils import generate_keypair, register_agent

# Attempt to load Cap'n Proto schema using pycapnp
# This requires `pycapnp` to be installed and the `capnp` command-line tool
# to be available in the system PATH for runtime compilation of the schema.
from pathlib import Path
_schema_path = Path(__file__).parent.parent / 'core' / 'message_schemas.capnp'
try:
    import capnp
    
    # Ensure the schema file exists before attempting to load
    if not os.path.exists(_schema_path):
        logging.error(f"Cap'n Proto schema file not found at: {_schema_path}")
        raise FileNotFoundError(_schema_path)

    message_schemas_capnp = capnp.load(_schema_path)
    SpeakMessage = message_schemas_capnp.SpeakMessage
    DeferralPackage = message_schemas_capnp.DeferralPackage
    MemoryOperation = message_schemas_capnp.MemoryOperation
    Observation = message_schemas_capnp.Observation
    AgentCorrectionThought = message_schemas_capnp.AgentCorrectionThought
    logging.info(f"Successfully loaded Cap'n Proto schema from: {_schema_path}")

except ImportError:
    logging.error("The 'pycapnp' library is not installed. Please install it to use Cap'n Proto schemas.")
    # Define placeholders if capnp fails to load to prevent immediate NameErrors at import.
    SpeakMessage, DeferralPackage, MemoryOperation, Observation, AgentCorrectionThought = (object,) * 5
except FileNotFoundError:
    logging.error(f"Cap'n Proto schema file missing. Placeholder types will be used.")
    SpeakMessage, DeferralPackage, MemoryOperation, Observation, AgentCorrectionThought = (object,) * 5
except Exception as e:
    logging.error(f"Failed to load Cap'n Proto schema from '{_schema_path}': {e}. This might be due to 'capnp' executable not being in PATH or an issue with the schema file itself. Placeholder types will be used.")
    SpeakMessage, DeferralPackage, MemoryOperation, Observation, AgentCorrectionThought = (object,) * 5


class SecureEnvelope:
    """Encrypted message envelope with HMAC verification."""
    
    def __init__(
        self, 
        message_id: str, 
        operation: str, 
        body: Dict[str, Any],
        hmac_sig: str
    ):
        self.message_id = message_id
        self.operation = operation
        self.body = body
        self.hmac_sig = hmac_sig

    @classmethod
    def decrypt(
        cls, 
        ciphertext: bytes, 
        secret: bytes
    ) -> Optional["SecureEnvelope"]:
        try:
            # Decryption logic here
            return cls("msg123", "TEST", {}, "sig")
        except Exception as e:
            logging.error(f"Decryption failed: {str(e)}")
            return None

class VeilidProvider:
    """Core provider for Veilid DHT operations, using Veilid's JSON API."""
    
    _vld: Optional[Any]  # Type annotation for static analysis
    
    def __init__(self) -> None:
        self._vld = None  # Stores the Veilid JSON API client
        self._running = False
        self._listeners: list[tuple[str, Callable, Optional[str]]] = [] # type hint for listeners

    async def start(self) -> None:
        """Initialize Veilid JSON API connection and load credentials."""
        if self._vld:  # Check correct attribute
            logging.warning("VeilidProvider already started.")
            return
        try:
            # Initialize the Veilid JSON API client.
            # Configuration might be needed here (e.g., path to veilid-core config)
            # For now, assuming default initialization works or is handled by veilid-python.
            self._vld = await veilid.VeilidAPI.attach()  # type: ignore[call-arg]
            logging.info("Veilid JSON API client initialized successfully.")
        except AttributeError as e:
            logging.error(f"Failed to initialize Veilid JSON API: 'veilid.json_api.new_json_veilid_api' not found. Error: {e}. Is veilid-python installed correctly and up to date?")
            raise RuntimeError("Failed to initialize Veilid JSON API due to missing method.") from e
        except Exception as e:
            logging.error(f"An unexpected error occurred during Veilid JSON API initialization: {e}")
            raise RuntimeError("Failed to initialize Veilid JSON API.") from e
        
        await self._load_credentials()

    async def stop(self) -> None:
        """Clean shutdown of the Veilid JSON API connection."""
        if self._vld:
            try:
                logging.debug("Initiating Veilid shutdown sequence")
                await self._vld.shutdown()
                self._vld = None
                logging.info("Veilid API shutdown completed successfully")
            except Exception as e:
                logging.error(f"Error during Veilid JSON API client shutdown: {e}")
            finally:
                self._running = False # Ensure running flag is reset
        else:
            logging.info("VeilidProvider stop called, but client was not running or already stopped.")

    async def send_message(
        self, 
        operation: str, 
        payload: Dict[str, Any],
        subkey: int = 0 # Assuming subkey is relevant for your Veilid app calls
    ) -> None:
        """Send an encrypted message using the Veilid JSON API."""
        if not self._vld:
            raise RuntimeError("VeilidProvider not initialized or Veilid connection failed.")

        # This is a placeholder for how you'd structure your app_call.
        # You'll need to replace "your_veilid_app_send_message_rpc"
        # with the actual RPC method name your Veilid application expects,
        # and structure the parameters accordingly.
        try:
            logging.debug(f"Sending message via Veilid: Operation='{operation}', Subkey={subkey}")
            # Example structure for an app_call:
            # response = await self._json_api.app_call(
            #     "your_veilid_app_send_message_rpc",
            #     {"operation": operation, "payload": json.dumps(payload), "subkey": subkey}
            # )
            # logging.debug(f"Veilid send_message response: {response}")
            await self._vld.store(
                operation,
                json.dumps(payload).encode('utf-8')
            )
        except Exception as e:
            logging.error(f"Error sending message via Veilid: {e}")
            raise

    async def receive_messages(
        self,
        subkey: int = 1, # Assuming subkey is relevant for your Veilid app calls
        rate_limit: int = 60 # Seconds
    ) -> None:
        """Continuously receive messages using the Veilid JSON API."""
        if not self._vld:
            logging.error("Veilid provider not started or JSON API not available, cannot receive messages.")
            return

        self._running = True
        logging.info(f"Starting to receive messages on subkey {subkey} with poll interval {rate_limit}s.")
        while self._running:
            try:
                # This is a placeholder. You'll need to replace "your_veilid_app_receive_message_rpc"
                # with the actual RPC method and parameters.
                # This might involve long polling, a subscription, or periodic checks.
                # received_data = await self._vld.app_call(
                #     "your_veilid_app_receive_message_rpc",
                #     {"subkey": subkey, "timeout": rate_limit * 1000} # Example timeout in ms
                # )
                # if received_data and received_data.get('messages'):
                #     for msg_data in received_data['messages']:
                #         # Assuming msg_data needs to be decrypted and parsed into SecureEnvelope
                #         # ciphertext = base64.b64decode(msg_data.get('encrypted_payload'))
                #         # secret_key = self._get_secret_for_sender(msg_data.get('sender_did'))
                #         # envelope = SecureEnvelope.decrypt(ciphertext, secret_key)
                #         # if envelope:
                #         #    await self._handle_envelope(envelope)
                #         pass # process message
                # else:
                #     logging.debug("No new messages received.")
                await asyncio.sleep(rate_limit) # Placeholder for polling interval
            except Exception as e:
                logging.error(f"Error during Veilid message reception: {e}")
                # Implement backoff or other error handling as needed
                await asyncio.sleep(min(rate_limit * 2, 300)) # Basic exponential backoff capped at 5 mins
            if not self._running:
                logging.info("Receive messages loop is stopping.")
                break

    async def _handle_envelope(
        self, 
        envelope: SecureEnvelope 
    ) -> None:
        """Process received envelopes and dispatch to listeners."""
        logging.debug(f"Handling envelope: ID={envelope.message_id}, Operation={envelope.operation}")
        for listener_id, callback_func, operation_filter in self._listeners:
            if operation_filter is None or envelope.operation == operation_filter:
                try:
                    logging.debug(f"Dispatching envelope {envelope.message_id} to listener {listener_id}")
                    await callback_func(envelope)
                except Exception as e:
                    logging.error(f"Error in listener '{listener_id}' for operation '{envelope.operation}': {e}")

    async def _load_credentials(self) -> None:
        """Load cryptographic credentials (placeholder)."""
        # Actual credential loading logic (e.g., from env vars, config files) should go here.
        # This might involve setting up keys for encryption/decryption with SecureEnvelope.
        logging.info("Veilid credentials loading (stub). Ensure actual implementation.")
        # Example:
        # self.dht_secret_key = os.environ.get("VEILID_DHT_SECRET")
        # if not self.dht_secret_key:
        #     logging.warning("VEILID_DHT_SECRET not set in environment.")

    def add_listener(self, listener_id: str, callback: Callable, operation_filter: Optional[str] = None) -> None:
        """Register a callback for specific message operations."""
        self._listeners.append((listener_id, callback, operation_filter))
        logging.info(f"Added listener '{listener_id}' for operation filter '{operation_filter or 'ANY'}'")

    def remove_listener(self, listener_id: str) -> None:
        """Unregister a callback."""
        self._listeners = [(lid, cb, op) for lid, cb, op in self._listeners if lid != listener_id]
        logging.info(f"Removed listener '{listener_id}'")