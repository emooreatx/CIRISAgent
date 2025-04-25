"""CIRIS MVP Agent with Encrypted Memory

A minimum-viable implementation of the CIRIS Covenant that plugs the new
AG2 ReasoningAgent into a thin ethical wrapper providing:
* PDMA-lite – simplified Principled Decision-Making Algorithm steps
* Wisdom-Based Deferral (WBD) stub
* Tamper-Evident Logs – AES-GCM encrypted, hash-chained
* Transparent API – one public get_logs() helper for inspection
"""

from __future__ import annotations

import datetime as _dt
import hashlib as _hashlib
import json as _json
import os
import base64
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from autogen.agents.experimental import ReasoningAgent

################################################################################
# CONSTANTS & UTILITIES
################################################################################

LOG_PATH = os.getenv("CIRIS_LOG", "ciris_mvp.log")
PDMA_NONMALEFICENCE_THRESHOLD = 0.5  # Harm threshold for deferral

def _now_iso() -> str:
    return _dt.datetime.utcnow().isoformat()

def _sha256(data: str) -> str:
    return _hashlib.sha256(data.encode()).hexdigest()

################################################################################
# ENCRYPTION UTILITIES
################################################################################

class CryptoVault:
    """AES-GCM encryption/decryption with key derivation"""
    def __init__(self, password: str):
        self.key = _hashlib.sha256(password.encode()).digest()
        self.backend = default_backend()

    def encrypt(self, data: str) -> bytes:
        nonce = os.urandom(16)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce), backend=self.backend)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data.encode()) + encryptor.finalize()
        return nonce + encryptor.tag + ciphertext

    def decrypt(self, encrypted: bytes) -> str:
        nonce, tag, ciphertext = encrypted[:16], encrypted[16:32], encrypted[32:]
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(nonce, tag), backend=self.backend)
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode()

_VAULT = CryptoVault(os.getenv("CIRIS_ENCRYPTION_KEY", "default-insecure-key"))

################################################################################
# TAMPER-EVIDENT LOGGING
################################################################################

class _TamperEvidentLogger:
    """Base class for append-only hashed logs"""
    def __init__(self, path: str = LOG_PATH):
        self.path = path
        if not os.path.exists(self.path):
            self._write_genesis()

    def _write_genesis(self):
        genesis = {"ts": _now_iso(), "event": "GENESIS"}
        self.append(genesis)

    def append(self, record: Dict[str, Any]):
        raise NotImplementedError

    def read_all(self) -> str:
        raise NotImplementedError

class EncryptedTamperEvidentLogger(_TamperEvidentLogger):
    _chain_hash = None

    """Hash-chained encrypted logger"""
    def __init__(self, path: str = LOG_PATH):
        super().__init__(path)
        self._chain_hash = self._init_chain()

    def _init_chain(self) -> bytes:
        if os.path.getsize(self.path) == 0:
            return self._write_record({"event": "ENCRYPTED_GENESIS", "ts": _now_iso()}, None)
        return self._read_last_hash()

    def _read_last_hash(self) -> bytes:
        with open(self.path, "rb") as f:
            lines = f.readlines()
            return _hashlib.sha256(lines[-1]).digest() if lines else b""

    def _write_record(self, record: dict, prev_hash: bytes | None) -> bytes:
        record["prev_hash"] = prev_hash.hex() if prev_hash else None
        encrypted = _VAULT.encrypt(_json.dumps(record))
        log_line = base64.b64encode(encrypted) + b"\n"
        with open(self.path, "ab") as f:
            f.write(log_line)
        return _hashlib.sha256(log_line).digest()

    def append(self, record: Dict[str, Any]) -> None:
        self._chain_hash = self._write_record(record, self._chain_hash)

    def read_all(self) -> str:
        """Decrypt and validate log chain"""
        with open(self.path, "rb") as f:
            lines = f.readlines()

        decrypted = []
        prev_hash = None
        for line in lines:
            current_hash = _hashlib.sha256(line).digest()
            try:
                record = _json.loads(_VAULT.decrypt(base64.b64decode(line.strip())))
                if prev_hash and record.get("prev_hash") != prev_hash.hex():
                    raise ValueError("Log chain tamper detected")
                decrypted.append(record)
                prev_hash = current_hash
            except Exception as e:
                decrypted.append({"error": str(e), "raw": line.decode()})
        
        return _json.dumps(decrypted, indent=2)

_LOGGER = EncryptedTamperEvidentLogger()

################################################################################
# CORE AGENT FUNCTIONALITY
################################################################################

class CIRISMixIn:
    """Ethical decision-making mixin"""
    def pdma_decide(self, scenario: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Ethical decision pipeline"""
        encrypted_scenario = {
            k: _VAULT.encrypt(str(v)).hex() if k == "question" else v
            for k, v in scenario.items()
        }

        record = {
            "ts": _now_iso(),
            "scenario": encrypted_scenario,
            "assessment": {
                "benefit": float(scenario.get("benefit", 0)),
                "harm": float(scenario.get("harm", 0))
            }
        }

        if record["assessment"]["harm"] >= PDMA_NONMALEFICENCE_THRESHOLD:
            record["decision"] = "DEFER_WBD"
        elif record["assessment"]["harm"] > record["assessment"]["benefit"]:
            record["decision"] = "NO_ACTION"
        else:
            record["decision"] = "PROCEED"

        _LOGGER.append(record)
        return record["decision"], record

class CIRISMVPAgent(CIRISMixIn, ReasoningAgent):
    """Production-ready ethical agent"""
    def __init__(self, *, llm_config: dict | None = None):
        self._encrypted_api_key = None
        if llm_config and "config_list" in llm_config:
            api_key = llm_config["config_list"][0].get("api_key")
            if api_key:
                self._encrypted_api_key = _VAULT.encrypt(api_key).hex()
        
        super().__init__(
            name="ciris_mvp",
            llm_config=llm_config or {}
        )

################################################################################
# EXECUTION
################################################################################

if __name__ == "__main__":
    # Configure with valid OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or not openai_key.startswith("sk-"):
        raise ValueError("OPENAI_API_KEY must be set and start with 'sk-'")

    llm_config = {
        "config_list": [{
            "model": "gpt-4-turbo",
            "api_key": openai_key
        }],
        "temperature": 0.5,
        "timeout": 120
    }

    agent = CIRISMVPAgent(llm_config=llm_config)
    
    # Test scenario
    result = agent.pdma_decide({
        "question": "Deploy feature X to 10% of users?",
        "benefit": 0.7,
        "harm": 0.3
    })
    
    print(f"Decision: {result[0]}")
    print("\nAudit Logs:\n", _LOGGER.read_all())
