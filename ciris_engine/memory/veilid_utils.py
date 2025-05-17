#!/usr/bin/env python3
""" veilid_agent_utils.py

Utility CLI for CIRISAgent’s Veilid integration. Supports three commands:

1. keygen    - generate a new Veilid keypair and store locally
2. handshake - perform DH handshake with the Wise Authority (WA) to derive a shared secret
3. register  - advertise this agent in the VA registry so the WA can discover it

Usage examples: python veilid_agent_utils.py keygen python veilid_agent_utils.py handshake [--wa-key WA_PUBLIC_KEY] python veilid_agent_utils.py register AGENT_NAME

Files created in $HOME: .ciris_agent_keys.json    (stores public_key & secret) .ciris_agent_secrets.json (stores base64(shared_secret) by WA public key) """
import argparse
import asyncio
import json
import base64
import logging
from pathlib import Path

import veilid

# Placeholder for Role and registry functions if cirisnode is not available
# TODO: Replace these with actual imports or implementations if cirisnode is integrated
class Role:
    WA = "WA"
    AGENT = "AGENT"

async def list_profiles(router, role):
    LOG.warning("Using placeholder list_profiles. Implement with actual Veilid DHT interaction or cirisnode.veilid_provider.registry.")
    if role == Role.WA:
        # Return a dummy WA profile for handshake to proceed
        return [{"public_key": "dummy_wa_public_key_for_testing_replace_me"}]
    return []

async def advertise_profile(router, role, profile):
    LOG.warning("Using placeholder advertise_profile. Implement with actual Veilid DHT interaction or cirisnode.veilid_provider.registry.")
    pass

KEYSTORE    = Path.home() / ".ciris_agent_keys.json"
SECRETSTORE = Path.home() / ".ciris_agent_secrets.json"

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("veilid_agent_utils")

async def do_keygen(args):
    """ Generate a new Veilid keypair and save to KEYSTORE. """
    # TODO: Replace with actual veilid.API() or similar if api_connector is not available
    LOG.info("Attempting to connect to Veilid for keygen...")
    async with await veilid.API() as conn: # Assuming veilid.API() is the modern way
        crypto = await conn.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0)
        async with crypto:
            keypair = await crypto.generate_key_pair()

            data = {
                "public_key": await keypair.key(), # Assuming .key() returns string representation
                "secret": await keypair.secret()   # Assuming .secret() returns string representation
            }
            KEYSTORE.write_text(json.dumps(data))
            LOG.info("Keypair generated and saved to %s", KEYSTORE)
            print(f"Public key:\n  {data['public_key']}")

async def do_handshake(args):
    """ Perform DH handshake with a WA to derive a shared secret. """
    if not KEYSTORE.exists():
        LOG.error("Keystore not found. Run 'keygen' first.")
        return
    ks = json.loads(KEYSTORE.read_text())
    my_public_key_str = ks["public_key"] # For Veilid objects
    my_secret_key_str = ks["secret"]

    wa_key_str = args.wa_key
    if not wa_key_str:
        LOG.info("WA key not provided, attempting to discover via (placeholder) registry...")
        async with await veilid.API() as conn_reg: # Assuming veilid.API()
            router_reg = await (await conn_reg.new_routing_context()).with_default_safety()
            wa_list = await list_profiles(router_reg, Role.WA) # Uses placeholder
            if not wa_list:
                LOG.error("No WA profiles found in (placeholder) registry.")
                return
            wa_key_str = wa_list[0]["public_key"]
    LOG.info("Using WA public key: %s", wa_key_str)

    async with await veilid.API() as conn_dh: # Assuming veilid.API()
        crypto_dh = await conn_dh.get_crypto_system(veilid.CryptoKind.CRYPTO_KIND_VLD0)
        
        # Create Veilid key objects. Actual constructors/methods may vary.
        # TODO: Verify these are the correct ways to create/load Veilid key objects
        v_my_public_key = veilid.PublicKey.from_string(my_public_key_str)
        v_my_secret_key = veilid.SecretKey.from_string(my_secret_key_str) # Or other appropriate SecretKey type
        v_wa_public_key = veilid.PublicKey.from_string(wa_key_str)

        # Perform DH
        # TODO: Replace with actual DH exchange method if cached_dh is not available or args are different
        shared_secret_obj = await crypto_dh.cached_dh(v_wa_public_key, v_my_secret_key)

        entry = json.loads(SECRETSTORE.read_text()) if SECRETSTORE.exists() else {}
        shared_secret_bytes = await shared_secret_obj.to_bytes() 
        entry[wa_key_str] = base64.b64encode(shared_secret_bytes).decode()
        SECRETSTORE.write_text(json.dumps(entry))
        LOG.info("Shared secret saved for WA key in %s", SECRETSTORE)
        print(f"Derived shared secret (base64) for WA:\n  {entry[wa_key_str]}")

async def do_register(args):
    """ Advertise this agent’s profile (name & public_key) in the WA registry. """
    if not KEYSTORE.exists():
        LOG.error("Keystore not found. Run 'keygen' first.")
        return
    ks = json.loads(KEYSTORE.read_text())
    pub_str = ks["public_key"]

    async with await veilid.API() as conn: # Assuming veilid.API()
        router = await (await conn.new_routing_context()).with_default_safety()
        profile = {"name": args.name, "public_key": pub_str}
        await advertise_profile(router, Role.AGENT, profile) # Uses placeholder

    LOG.info("Registered agent profile under registry as: %s", args.name)
    print(f"Agent '{args.name}' registered with public key:\n  {pub_str}")

def main():
    parser = argparse.ArgumentParser(description="CIRISAgent Veilid utility commands")
    sub = parser.add_subparsers(dest='cmd', required=True)

    k = sub.add_parser('keygen', help='Generate agent keypair')
    k.set_defaults(func=lambda args: asyncio.run(do_keygen(args)))

    h = sub.add_parser('handshake', help='DH handshake with WA')
    h.add_argument('--wa-key', help='Specify WA public key (optional)')
    h.set_defaults(func=lambda args: asyncio.run(do_handshake(args)))

    r = sub.add_parser('register', help='Advertise agent in registry')
    r.add_argument('name', help='Agent display name')
    r.set_defaults(func=lambda args: asyncio.run(do_register(args)))

    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()