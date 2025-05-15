#!/usr/bin/env python3 """ veilid_agent_utils.py

Utility CLI for CIRISAgent’s Veilid integration. Supports three commands:

1. keygen    - generate a new Veilid keypair and store locally


2. handshake - perform DH handshake with the Wise Authority (WA) to derive a shared secret


3. register  - advertise this agent in the VA registry so the WA can discover it



Usage examples: python veilid_agent_utils.py keygen python veilid_agent_utils.py handshake [--wa-key WA_PUBLIC_KEY] python veilid_agent_utils.py register AGENT_NAME

Files created in $HOME: .ciris_agent_keys.json    (stores public_key & secret) .ciris_agent_secrets.json (stores base64(shared_secret) by WA public key) """ import argparse import asyncio import json import base64 import logging from pathlib import Path

import veilid from cirisnode.veilid_provider.registry import advertise_profile, list_profiles, Role

Paths for local storage

KEYSTORE    = Path.home() / ".ciris_agent_keys.json" SECRETSTORE = Path.home() / ".ciris_agent_secrets.json"

Setup logging

logging.basicConfig(level=logging.INFO) LOG = logging.getLogger("veilid_agent_utils")

async def do_keygen(args): """ Generate a new Veilid keypair and save to KEYSTORE. """ conn = await veilid.api_connector(lambda *a, **k: None) crypto = await conn.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0) async with crypto: keypair = await crypto.generate_key_pair()

# Persist keys
data = {
    "public_key": keypair.key(),
    "secret": keypair.secret()
}
KEYSTORE.write_text(json.dumps(data))
LOG.info("Keypair generated and saved to %s", KEYSTORE)
print(f"Public key:\n  {data['public_key']}")
await conn.close()

async def do_handshake(args): """ Perform DH handshake with a WA to derive a shared secret. If --wa-key is not provided, will pick the first WA from the registry. """ # Load agent secret if not KEYSTORE.exists(): LOG.error("Keystore not found. Run 'keygen' first.") return ks = json.loads(KEYSTORE.read_text()) my_secret = ks["secret"]

# Determine WA public key
if args.wa_key:
    wa_key = args.wa_key
else:
    # Discover WA via registry
    conn = await veilid.api_connector(lambda *a, **k: None)
    router = await (await conn.new_routing_context()).with_default_safety()
    wa_list = await list_profiles(router, Role.WA)
    await conn.close()
    if not wa_list:
        LOG.error("No WA profiles found in registry.")
        return
    wa_key = wa_list[0]["public_key"]
LOG.info("Using WA public key: %s", wa_key)

# Derive shared secret
conn = await veilid.api_connector(lambda *a, **k: None)
crypto = await conn.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0)
secret = await crypto.cached_dh(wa_key, my_secret)
await conn.close()

# Store shared secret (base64) under WA key
entry = json.loads(SECRETSTORE.read_text()) if SECRETSTORE.exists() else {}
entry[wa_key] = base64.b64encode(secret.to_bytes()).decode()
SECRETSTORE.write_text(json.dumps(entry))
LOG.info("Shared secret saved for WA key in %s", SECRETSTORE)
print(f"Derived shared secret (base64) for WA:\n  {entry[wa_key]}")

async def do_register(args): """ Advertise this agent’s profile (name & public_key) in the WA registry. Requires the keystore to exist. """ if not KEYSTORE.exists(): LOG.error("Keystore not found. Run 'keygen' first.") return ks = json.loads(KEYSTORE.read_text()) pub = ks["public_key"]

# Connect and advertise
conn = await veilid.api_connector(lambda *a, **k: None)
router = await (await conn.new_routing_context()).with_default_safety()
profile = {"name": args.name, "public_key": pub}
await advertise_profile(router, Role.AGENT, profile)
await conn.close()

LOG.info("Registered agent profile under registry as: %s", args.name)
print(f"Agent '{args.name}' registered with public key:\n  {pub}")

def main(): parser = argparse.ArgumentParser( description="CIRISAgent Veilid utility commands" ) sub = parser.add_subparsers(dest='cmd', required=True)

# keygen
k = sub.add_parser('keygen', help='Generate agent keypair')
k.set_defaults(func=lambda args: asyncio.run(do_keygen(args)))

# handshake
h = sub.add_parser('handshake', help='DH handshake with WA')
h.add_argument('--wa-key', help='Specifiy WA public key (optional)')
h.set_defaults(func=lambda args: asyncio.run(do_handshake(args)))

# register
r = sub.add_parser('register', help='Advertise agent in registry')
r.add_argument('name', help='Agent display name')
r.set_defaults(func=lambda args: asyncio.run(do_register(args)))

args = parser.parse_args()
args.func(args)

if name == 'main': main()

