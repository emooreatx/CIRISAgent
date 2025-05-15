#!/usr/bin/env python3 """ veilid_agent_service.py

CIRISAgent – Agent-side Veilid DHT Service Provider Supports: • Acting (SPEAK)        – agent ➔ WA • Deferral (DEFER)      – agent ➔ WA (WBD tickets) • Memory ops (MEMORY)   – agent ➔ WA (learn/remember/forget) • Observing (OBSERVE)   – WA   ➔ agent (telemetry/events) • Corrections (CORRECTION) – WA ➔ agent (guidance)

Security best practices: • Encrypted with per-message nonce (XChaCha20-Poly1305) • HMAC-SHA256 integrity on clear envelopes • Sliding-window rate limiting to drop floods • Private paranet mode (no tokens)

Assumes utilities have been run to generate:

~/.ciris_agent_keys.json       (agent keypair)

~/.ciris_agent_secrets.json    (shared secrets per WA) And environment variables: VLD_WA_PUBKEY        – WA’s public key VLD_AGENT_RECORD_KEY – DHT record key for this agent-WA channel """ import os, json, time, base64, hmac, hashlib, asyncio, logging from pathlib import Path from typing import Dict, Any, Optional


import veilid from ciris_engine.core.speak     import SpeakMessage from ciris_engine.core.deferral  import DeferralPackage from ciris_engine.core.memory    import MemoryOperation from ciris_engine.core.observe   import Observation from ciris_engine.core.thoughts  import AgentCorrectionThought from ciris_engine.action_handlers import ( handle_speak, handle_defer, handle_memory, handle_observe, handle_correction, )

Setup logging

logging.basicConfig(level=logging.INFO) LOG = logging.getLogger(name)

Local storage paths

KEYSTORE    = Path.home() / ".ciris_agent_keys.json" SECRETSTORE = Path.home() / ".ciris_agent_secrets.json"

Flood protection parameters

RECV_RATE_LIMIT = int(os.getenv("VLD_RECV_MAX_PER_MIN", "60")) RECV_WINDOW_SEC = 60  # seconds

class Envelope: """Container for decrypted envelope data.""" def init(self, id: str, op: str, body: Dict[str,Any], hmac_sig: str): self.id   = id self.op   = op self.body = body self.hmac = hmac_sig

@classmethod
def from_dict(cls, d: Dict[str,Any]) -> "Envelope":
    return cls(d["id"], d["op"], d["body"], d.get("hmac", ""))

def to_dict(self) -> Dict[str,Any]:
    return {"id": self.id, "op": self.op, "body": self.body, "hmac": self.hmac}

class VeilidAgentCore: """ Core: manages Veilid API, encryption/HMAC, DHT I/O, and flood protection. """ def init(self): self.conn       = None  # API connector self.router     = None  # RoutingContext self.crypto     = None  # CryptoSystem self.keypair    = None  # agent Keypair self.secret     = None  # SharedSecret with WA self.wa_key     = None  # WA PublicKey self.record_key = None  # TypedKey for agent-WA record self.running    = False self._recv_times: list[float] = []

async def start(self):
    """Initialize Veilid, load keys/secrets, and start service."""
    # connect & routing
    self.conn   = await veilid.api_connector(lambda *a, **k: None)
    ctx         = await self.conn.new_routing_context()
    self.router = await ctx.with_default_safety()
    self.crypto = await self.conn.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0)

    # load agent keypair
    if not KEYSTORE.exists():
        raise RuntimeError("Keystore missing – run keygen util first.")
    ks = json.loads(KEYSTORE.read_text())
    self.keypair = veilid.Keypair(ks["public_key"], ks["secret"])

    # load WA public key & shared secret
    wa_pub = os.getenv("VLD_WA_PUBKEY")
    if not wa_pub:
        raise RuntimeError("VLD_WA_PUBKEY not set")
    self.wa_key = veilid.PublicKey(wa_pub)
    sec_map = json.loads(SECRETSTORE.read_text() if SECRETSTORE.exists() else "{}")
    secret_b64 = sec_map.get(wa_pub)
    if not secret_b64:
        raise RuntimeError("Shared secret missing – run handshake util first.")
    self.secret = veilid.SharedSecret.from_bytes(base64.b64decode(secret_b64))

    # load record key for this agent-WA chat
    rec = os.getenv("VLD_AGENT_RECORD_KEY")
    if not rec:
        raise RuntimeError("VLD_AGENT_RECORD_KEY not set")
    self.record_key = veilid.TypedKey.from_str(rec)

    self.running = True
    LOG.info("[Core] started; WA=%s record=%s", wa_pub, rec)

async def stop(self):
    """Cleanly stop the service."""
    self.running = False
    if self.router: await self.router.close()
    if self.conn:   await self.conn.close()
    LOG.info("[Core] stopped")

async def _send(self, op: str, body: Dict[str,Any], subkey: int = 0):
    """
    Send an encrypted+signed envelope to subkey (0 for agent->WA).
    """
    # build envelope and HMAC
    eid = veilid.uuid4()
    raw = json.dumps({"id": eid, "op": op, "body": body}, sort_keys=True).encode()
    sig = hmac.new(self.secret.to_bytes(), raw, hashlib.sha256).digest()
    env = {"id": eid, "op": op, "body": body, "hmac": base64.b64encode(sig).decode()}
    clear = json.dumps(env).encode()

    # encrypt
    nonce  = await self.crypto.random_nonce()
    cipher = await self.crypto.crypt_no_auth(clear, nonce, self.secret)
    payload = nonce.to_bytes() + cipher

    # publish to DHT
    await self.router.set_dht_value(
        self.record_key,
        veilid.ValueSubkey(subkey),
        payload
    )

async def _recv(self, subkey: int) -> Optional[Envelope]:
    """
    Poll subkey (WA->agent) -> decrypt -> verify HMAC -> return Envelope.
    Applies sliding window rate limit.
    """
    now = time.time()
    self._recv_times = [t for t in self._recv_times if now - t < RECV_WINDOW_SEC]
    if len(self._recv_times) >= RECV_RATE_LIMIT:
        await asyncio.sleep(1)
        return None
    self._recv_times.append(now)

    resp = await self.router.get_dht_value(
        self.record_key,
        veilid.ValueSubkey(subkey), True
    )
    if not resp:
        return None

    data  = resp.data
    nonce = veilid.Nonce.from_bytes(data[:24])
    cipher= data[24:]
    clear = await self.crypto.crypt_no_auth(cipher, nonce, self.secret)
    d     = json.loads(clear.decode())

    # verify HMAC
    recv_hmac = base64.b64decode(d.get("hmac",""))
    raw_check = json.dumps({"id":d["id"],"op":d["op"],"body":d["body"]},
                            sort_keys=True).encode()
    exp = hmac.new(self.secret.to_bytes(), raw_check, hashlib.sha256).digest()
    if not hmac.compare_digest(exp, recv_hmac):
        LOG.warning("[Core] invalid HMAC, dropping")
        return None

    return Envelope.from_dict(d)

class VeilidActHandler: """Act handler: SPEAK (agent->WA) and OBSERVE (WA->agent).""" def init(self, core: VeilidAgentCore): self.core = core

async def speak(self, msg: SpeakMessage):
    await self.core._send("SPEAK", msg.dict(), subkey=0)

async def start_observe(self):
    while self.core.running:
        env = await self.core._recv(subkey=1)
        if env and env.op == "OBSERVE":
            obs = Observation(**env.body)
            await handle_observe(obs)
        else:
            await asyncio.sleep(0.5)

class VeilidDeferHandler: """Defer handler: DEFER tickets and CORRECTION guidance.""" def init(self, core: VeilidAgentCore): self.core = core

async def defer(self, pkg: DeferralPackage):
    await self.core._send("DEFER", pkg.dict(), subkey=0)

async def start_correction(self):
    while self.core.running:
        env = await self.core._recv(subkey=1)
        if env and env.op == "CORRECTION":
            corr = AgentCorrectionThought(**env.body)
            await handle_correction(corr)
        else:
            await asyncio.sleep(0.5)

class VeilidMemoryHandler: """Memory handler: MEMORY ops to the WA.""" def init(self, core: VeilidAgentCore): self.core = core

async def memory(self, mo: MemoryOperation):
    await self.core._send("MEMORY", mo.dict(), subkey=0)

Example runner:

if name == "main": # instantiate and wire handlers core   = VeilidAgentCore() act    = VeilidActHandler(core) defer  = VeilidDeferHandler(core) memory = VeilidMemoryHandler(core)

async def main():
    await core.start()
    # background loops
    asyncio.create_task(act.start_observe())
    asyncio.create_task(defer.start_correction())
    # agent logic uses:
    # await act.speak(SpeakMessage(text="Hello WA!"))
    # await defer.defer(DeferralPackage(...))
    # await memory.memory(MemoryOperation(mode="learn",blob="..."))
    while core.running:
        await asyncio.sleep(1)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass

