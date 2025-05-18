# CIRISAgent × Veilid 

> Status 2025‑05‑15 – design frozen, implementation underway.



This document explains how CIRISAgent will rely on Veilid — the encrypted, peer‑replicated DHT — to carry every agent/WA operation, secret, and consensus artefact. It supersedes the older “Veilid‑demo” notes.


---

## 1 The 9 Primary Options (+ Correction) | # | Option (op) | Direction | Purpose | DHT sub‑key | |--:|-------------|-----------|---------|-------------| | 1 | SPEAK | Agent → WA | Final / interim answers | 0 | | 2 | LISTEN | WA → Agent | Raw user/Discord text | 1 | | 3 | USE_TOOL | Agent → WA | Trigger external tool exec | 0 | | 4 | PONDER | WA → Agent | Inject a new thought | 1 | | 5 | DEFER | Agent → WA | Wisdom‑Based Deferral (WBD) ticket | 0 | | 6 | REJECT | Agent → WA | Decline task | 0 | | 7 | MEM_LEARN | Agent → WA | Store memory blob | 0 | | 8 | MEM_REMEMBER | WA → Agent | Recall memory blob | 1 | | 9 | MEM_FORGET | Agent → WA | Delete memory blob | 0 | | — | CORRECTION | WA → Agent | WA guidance / override | 1 |

All envelopes are encrypted + HMAC‑signed with the DH shared secret between the two parties ( see §4 ).


---

## 2 Record‑Key & Schema Conventions

VeilidKey(smpl:<session‑uuid>)          # core WA ⇄ Agent record
  ├─ subkey 0 • agent → WA              # SPEAK / DEFER / MEM_* / …
  └─ subkey 1 • WA → agent              # LISTEN / OBSERVE / CORRECTION / …

VeilidKey(smpl:<session>/secrets/<tok>)  # per‑secret vault entry

A fresh session record is created for each agent‑WA conversation and rotated ≥ daily.

Every write increments the Veilid seq ⟶ total ordering for light‑weight consensus.



---

## 3 Secret Handling Workflow

1. Strip & tokenise sensitive keys/values → __tok_x__.


2. Publish each (token,value) under …/secrets/<token> (encrypted).


3. Pass the sanitised envelope through DMA stacks (Guardrail → Ethics → CommonSense).


4. Post‑DMA, rehydrate by fetching the secret records with _recv_raw().



This keeps DMAs zero‑knowledge while allowing full reassembly.


---

## 4 Security Controls

Encryption – XChaCha20‑Poly1305 with random 24‑byte nonce per message.

Integrity – HMAC‑SHA256 over id+op+body, verified before JSON decode.

Flood Guard – sliding‑window rate‑limit (60 msgs/min) in Core.

Private Paranet – blockchain.enabled = false, so only CIRIS nodes gossip these records.



---

## 5 Light‑Weight Consensus (“TE‑seq”) Because every DHT write bumps the sequence number in Veilid, agents achieve a deterministic view by:

while True:
    resp = router.get_dht_value(key, sub, must_have_value=True)
    if resp.seq == expected_seq:  # all good
        break

If two agents race, the higher‑priority write simply produces the next seq; lower side re‑reads and merges.


---

## 6 Encoding & Query Layer

1. DHT triples stored as compact N‑Triples lines.


2. In‑process parser → Sparse adjacency & optional dense embedding.


3. GraphQL façade exposes node(id), neighbors, search(text) resolvers that hit the DHT and feed the encoding lib.



No external DB, no tokens, fully tamper‑evident.


---

## 7 Setup Summary

# Agent
python veilid_agent_utils.py   keygen
python veilid_agent_utils.py   handshake   # derive secret w/ WA
python veilid_agent_utils.py   register  MyAgent
export VLD_WA_PUBKEY=… VLD_AGENT_RECORD_KEY=…
python veilid_agent_service.py  # starts Core + handlers

# WA / CIRISNode
python veilid_node_utils.py    keygen
python veilid_node_utils.py    recordgen  --agent-key <pub>
python veilid_node_utils.py    handshake  --agent-key <pub>
python veilid_node_utils.py    register   CreatorWA
export VLD_WA_RECORD_KEY=…
python veilid_node_provider.py  # wisdom‑authority loop


---

## 8 Next Steps

1. Finish encoding‑lib PoC (RDF parse → vector embed).


2. Implement GraphQL resolvers backed by Veilid I/O.


3. Integrate secret‑strip / rehydrate hooks into Guardrail pipeline.


4. Load‑test flooding guards and seq‑based consensus under heavy chat.





✅ veilid.md added – a complete, up‑to‑date overview of:

How all 9 ops + Correction map to Veilid sub‑keys

Secrets stripping ➜ encrypted vault ➜ re‑hydration

Encryption, HMAC integrity, flood‑guard, and paranet isolation

Sequence‑number consensus (“TE‑seq”)

Lightweight RDF → GraphQL query layer

One‑shot setup commands for both Agent and WA


