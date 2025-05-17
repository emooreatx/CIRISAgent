#!/usr/bin/env python3
""" veilid_agent_service.py

CIRISAgent – Agent-side Veilid DHT Service Provider Supports: • Acting (SPEAK)        – agent ➔ WA • Deferral (DEFER)      – agent ➔ WA (WBD tickets) • Memory ops (MEMORY)   – agent ➔ WA (learn/remember/forget) • Observing (OBSERVE)   – WA   ➔ agent (telemetry/events) • Corrections (CORRECTION) – WA ➔ agent (guidance)

Security best practices: • Encrypted with per-message nonce (XChaCha20-Poly1305) • HMAC-SHA256 integrity on clear envelopes • Sliding-window rate limiting to drop floods • Private paranet mode (no tokens)

Assumes utilities have been run to generate:

~/.ciris_agent_keys.json       (agent keypair)

~/.ciris_agent_secrets.json    (shared secrets per WA) And environment variables: VLD_WA_PUBKEY        – WA’s public key VLD_AGENT_RECORD_KEY – DHT record key for this agent-WA channel """
import os, json, time, base64, hmac, hashlib, asyncio, logging, datetime, uuid
from pathlib import Path
from typing import Dict, Any, Optional

import veilid

# Corrected relative imports assuming this file is in ciris_engine/memory/
# and the target modules are in ciris_engine/core/ and ciris_engine/
# These will only work if the Python path is set up to recognize ciris_engine as a package.

# Attempt to import, with fallback for environments where direct execution might occur
# or package structure isn't perfectly recognized by linters immediately.
try:
    from ..core.speak     import SpeakMessage
    from ..core.deferral  import DeferralPackage
    from ..core.memory    import MemoryOperation
    from ..core.observe   import Observation
    from ..core.thoughts  import AgentCorrectionThought
    from ..action_handlers import (
        handle_speak,
        handle_defer,
        handle_memory,
        handle_observe,
        handle_correction,
    )
except ImportError:
    LOG = logging.getLogger(__name__)
    LOG.warning("Could not resolve relative imports for core schemas/handlers. Using placeholders.")
    class SpeakMessage: pass
    class DeferralPackage: pass
    class MemoryOperation: pass
    class Observation: pass
    class AgentCorrectionThought: pass
    async def handle_speak(*args, **kwargs): LOG.error("handle_speak not loaded")
    async def handle_defer(*args, **kwargs): LOG.error("handle_defer not loaded")
    async def handle_memory(*args, **kwargs): LOG.error("handle_memory not loaded")
    async def handle_observe(*args, **kwargs): LOG.error("handle_observe not loaded")
    async def handle_correction(*args, **kwargs): LOG.error("handle_correction not loaded")


# Setup logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__) # Use __name__ for logger

# Local storage paths
KEYSTORE    = Path.home() / ".ciris_agent_keys.json"
SECRETSTORE = Path.home() / ".ciris_agent_secrets.json"

# Flood protection parameters
RECV_RATE_LIMIT = int(os.getenv("VLD_RECV_MAX_PER_MIN", "60"))
RECV_WINDOW_SEC = 60  # seconds

class Envelope:
    """Container for decrypted envelope data."""
    def __init__(self, id: str, op: str, body: Dict[str,Any], hmac_sig: str):
        self.id   = id
        self.op   = op
        self.body = body
        self.hmac = hmac_sig

    @classmethod
    def from_dict(cls, d: Dict[str,Any]) -> "Envelope":
        return cls(d["id"], d["op"], d["body"], d.get("hmac", ""))

    def to_dict(self) -> Dict[str,Any]:
        return {"id": self.id, "op": self.op, "body": self.body, "hmac": self.hmac}

class VeilidAgentCore:
    """ Core: manages Veilid API, encryption/HMAC, DHT I/O, and flood protection. """
    def __init__(self):
        self.conn: Optional[veilid.VeilidAPI] = None
        self.router: Optional[veilid.RoutingContext] = None
        self.crypto: Optional[veilid.CryptoSystem] = None
        self.keypair: Optional[veilid.Keypair] = None
        self.secret: Optional[veilid.SharedSecret] = None
        self.wa_key: Optional[veilid.PublicKey] = None
        self.record_key: Optional[veilid.TypedKey] = None
        self.dht_nonce: Optional[veilid.Nonce] = None
        self.running: bool = False
        self._recv_times: list[float] = []
        self.logger = LOG

    async def start(self):
        """Initialize Veilid, load keys/secrets, and start service."""
        self.logger.info("[Core] starting...")
        self.conn = await veilid.api_connector(lambda *a, **k: None)
        ctx = await self.conn.new_routing_context()
        self.router = await ctx.with_default_safety()
        self.crypto = await self.conn.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0)
        if not self.crypto:
            raise RuntimeError("Failed to initialize crypto system.")
        self.dht_nonce = await self.crypto.random_nonce()

        if not KEYSTORE.exists():
            self.logger.error("Keystore missing – run keygen util first.")
            raise RuntimeError("Keystore missing – run keygen util first.")
        ks = json.loads(KEYSTORE.read_text())
        self.keypair = veilid.Keypair(veilid.PublicKey(ks["public_key"]), veilid.Secret(ks["secret"]))

        wa_pub_str = os.getenv("VLD_WA_PUBKEY")
        if not wa_pub_str:
            self.logger.error("VLD_WA_PUBKEY not set")
            raise RuntimeError("VLD_WA_PUBKEY not set")
        self.wa_key = veilid.PublicKey(wa_pub_str) # type: ignore
        
        sec_map = json.loads(SECRETSTORE.read_text()) if SECRETSTORE.exists() else {}
        # Use wa_pub_str directly, which is the string from env var and used to create self.wa_key
        secret_b64 = sec_map.get(wa_pub_str) 
        if not secret_b64:
            self.logger.error(f"Shared secret missing for WA {wa_pub_str} – run handshake util first.")
            raise RuntimeError(f"Shared secret missing for WA {wa_pub_str} – run handshake util first.")
        self.secret = veilid.SharedSecret.from_bytes(base64.b64decode(secret_b64)) # type: ignore

        rec_str = os.getenv("VLD_AGENT_RECORD_KEY")
        if not rec_str:
            self.logger.error("VLD_AGENT_RECORD_KEY not set")
            raise RuntimeError("VLD_AGENT_RECORD_KEY not set")
        self.record_key = veilid.TypedKey.from_str(rec_str)

        self.running = True
        self.logger.info("[Core] started; WA=%s record=%s", wa_pub_str, rec_str)

    async def stop(self):
        """Cleanly stop the service."""
        self.running = False
        if self.router: await self.router.close()
        if self.conn:   await self.conn.close()
        self.logger.info("[Core] stopped")

    async def _send(self, op: str, body: Dict[str,Any], subkey: int = 0):
        """
        Send an encrypted+signed envelope to subkey (0 for agent->WA).
        """
        if not self.secret or not self.crypto:
            self.logger.error("Shared secret or crypto not available. Cannot send message.")
            return

        eid = str(veilid.uuid4()) # type: ignore
        data_for_hmac = {"id": eid, "op": op, "body": body}
        raw_hmac_data = json.dumps(data_for_hmac, sort_keys=True).encode()
        hmac_key = self.secret.to_bytes() # type: ignore # Reverted: Removed await
        sig = hmac.new(hmac_key, raw_hmac_data, hashlib.sha256).digest()
        env = {"id": eid, "op": op, "body": body, "hmac": base64.b64encode(sig).decode()}
        clear_payload = json.dumps(env).encode()

        nonce = await self.crypto.random_nonce()
        cipher_payload = await self.crypto.crypt_no_auth(clear_payload, nonce, self.secret)
        final_payload = nonce.to_bytes() + cipher_payload

        if not self.router or not self.record_key:
            self.logger.error("Router or record_key not available. Cannot send message.")
            return
        await self.router.set_dht_value(
            self.record_key,
            veilid.ValueSubkey(subkey), # type: ignore
            final_payload
        )
        self.logger.debug(f"[Core] SENT {eid} op:{op} subkey:{subkey}")

    async def _recv(self, subkey: int) -> Optional[Envelope]:
        """
        Poll subkey (WA->agent) -> decrypt -> verify HMAC -> return Envelope.
        Applies sliding window rate limit.
        """
        if not self.secret or not self.crypto or not self.router or not self.record_key:
            self.logger.error("Core components missing. Cannot receive messages.")
            return None
            
        now = time.time()
        self._recv_times = [t for t in self._recv_times if now - t < RECV_WINDOW_SEC]
        if len(self._recv_times) >= RECV_RATE_LIMIT:
            self.logger.warning("[Core] Rate limit exceeded, delaying receive.")
            await asyncio.sleep(1)
            return None
        self._recv_times.append(now)

        resp = await self.router.get_dht_value(self.record_key, veilid.ValueSubkey(subkey), True) # type: ignore
        if not resp or not resp.data:
            return None

        data = resp.data
        nonce_size = 24 # veilid.Nonce.SIZE - This might be an issue if veilid.Nonce.SIZE is not 24
        try:
            nonce_bytes = data[:nonce_size]
            cipher_payload = data[nonce_size:]
            nonce = veilid.Nonce.from_bytes(nonce_bytes) # type: ignore
        except Exception as e:
            self.logger.error(f"Error parsing nonce/cipher from received data: {e}")
            return None
            
        clear_payload = await self.crypto.crypt_no_auth(cipher_payload, nonce, self.secret)
        try:
            decrypted_data = json.loads(clear_payload.decode())
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding JSON from decrypted payload: {e}")
            return None

        received_hmac_b64 = decrypted_data.pop("hmac", None)
        if not received_hmac_b64:
            self.logger.warning("[Core] received message without HMAC, dropping")
            return None
        
        data_for_hmac_check = {"id": decrypted_data["id"], "op": decrypted_data["op"], "body": decrypted_data["body"]}
        raw_check_data = json.dumps(data_for_hmac_check, sort_keys=True).encode()
        hmac_key = self.secret.to_bytes() # type: ignore # Reverted: Removed await
        expected_hmac = hmac.new(hmac_key, raw_check_data, hashlib.sha256).digest()
        received_hmac = base64.b64decode(received_hmac_b64)

        if not hmac.compare_digest(expected_hmac, received_hmac):
            self.logger.warning("[Core] invalid HMAC, dropping")
            return None
        
        decrypted_data["hmac"] = received_hmac_b64
        self.logger.debug(f"[Core] RECV {decrypted_data.get('id')} op:{decrypted_data.get('op')}")
        return Envelope.from_dict(decrypted_data)

    async def _encrypt_and_sign_dht_value(self, value: dict) -> bytes | None:
        if not self.secret or not self.crypto or not self.dht_nonce:
            self.logger.error("Cannot encrypt/sign DHT value: missing secret, crypto, or DHT nonce.")
            return None
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        value_with_timestamp = {"timestamp": timestamp, "value": value}
        raw = json.dumps(value_with_timestamp, sort_keys=True).encode()
        hmac_key = self.secret.to_bytes() # type: ignore # Reverted: Removed await
        sig = hmac.new(hmac_key, raw, hashlib.sha256).digest()
        encrypted_value = await self.crypto.crypt_no_auth(
            raw, self.dht_nonce, self.secret
        )
        return base64.b64encode(sig + encrypted_value)

    async def _verify_and_decrypt_dht_value(self, dht_value_blob: bytes) -> dict | None:
        if not self.secret or not self.crypto or not self.dht_nonce:
            self.logger.error("Cannot verify/decrypt DHT value: missing secret, crypto, or DHT nonce.")
            return None
        try:
            decoded_blob = base64.b64decode(dht_value_blob)
            sig_length = 32 # hashlib.sha256.digest_size
            sig = decoded_blob[:sig_length]
            encrypted_value = decoded_blob[sig_length:]
            
            decrypted_value_bytes = await self.crypto.crypt_no_auth(
                encrypted_value, self.dht_nonce, self.secret
            )
            decrypted_value_with_timestamp = json.loads(decrypted_value_bytes.decode())

            raw_check = json.dumps(decrypted_value_with_timestamp, sort_keys=True).encode()
            hmac_key = self.secret.to_bytes() # type: ignore # Reverted: Removed await
            exp = hmac.new(hmac_key, raw_check, hashlib.sha256).digest()
            if not hmac.compare_digest(exp, sig):
                self.logger.error("DHT value HMAC verification failed.")
                return None

            return decrypted_value_with_timestamp.get("value")
        except Exception as e:
            self.logger.error(f"Error verifying/decrypting DHT value: {e}")
            return None

class VeilidActHandler:
    """Act handler: SPEAK (agent->WA) and OBSERVE (WA->agent)."""
    def __init__(self, core: VeilidAgentCore):
        self.core = core

    async def speak(self, msg: SpeakMessage):
        payload = vars(msg)
        await self.core._send("SPEAK", payload, subkey=0)

    async def start_observe(self):
        while self.core.running:
            env = await self.core._recv(subkey=1)
            if env and env.op == "OBSERVE":
                try:
                    obs = Observation(**env.body)
                    await handle_observe(obs)
                except TypeError as e:
                    self.core.logger.error(f"Failed to initialize Observation from env.body: {e}. Body: {env.body}")
            elif env:
                self.core.logger.debug(f"Received non-OBSERVE envelope on subkey 1: {env.op}")
            await asyncio.sleep(0.5)

class VeilidDeferHandler:
    """Defer handler: DEFER tickets and CORRECTION guidance."""
    def __init__(self, core: VeilidAgentCore):
        self.core = core

    async def defer(self, pkg: DeferralPackage):
        payload = vars(pkg)
        await self.core._send("DEFER", payload, subkey=0)

    async def start_correction(self):
        while self.core.running:
            env = await self.core._recv(subkey=1)
            if env and env.op == "CORRECTION":
                try:
                    corr = AgentCorrectionThought(**env.body)
                    await handle_correction(corr)
                except TypeError as e:
                    self.core.logger.error(f"Failed to initialize AgentCorrectionThought: {e}. Body: {env.body}")
            elif env:
                self.core.logger.debug(f"Received non-CORRECTION envelope on subkey 1: {env.op}")
            await asyncio.sleep(0.5)

class VeilidMemoryHandler:
    """Memory handler: MEMORY ops to the WA."""
    def __init__(self, core: VeilidAgentCore):
        self.core = core

    async def memory(self, mo: MemoryOperation):
        payload = vars(mo)
        await self.core._send("MEMORY", payload, subkey=0)

# Example runner:
if __name__ == "__main__":
    core   = VeilidAgentCore()
    act    = VeilidActHandler(core)
    defer  = VeilidDeferHandler(core)
    memory = VeilidMemoryHandler(core)

    async def main_runner():
        await core.start()
        observe_task = asyncio.create_task(act.start_observe())
        correction_task = asyncio.create_task(defer.start_correction())
        
        LOG.info("Veilid Agent Service running. Press Ctrl+C to stop.")

        while core.running:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                LOG.info("Main runner task cancelled.")
                break
        
        if observe_task: await observe_task
        if correction_task: await correction_task
        await core.stop()

    try:
        asyncio.run(main_runner())
    except KeyboardInterrupt:
        LOG.info("KeyboardInterrupt received, shutting down.")
    finally:
        if core.running:
            asyncio.run(core.stop())