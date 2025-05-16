CIRIS DECP Implementation Roadmap

Milestones & Tasks

Milestone A – Core Governance

1) Form initial Wise‑Authority (WA) board (5 members) and publish disclosures.

2) Finalise escalation SLA table for WBD deferrals and circuit‑breaks.

3) Integrate WA signature verification in the agent runtime.


Milestone B – Emergency Kill Switches & Circuit-Breakers

1) Implement agent-local circuit-break logic, halting all outputs and actions on catastrophic PDMA/guardrail failure.

2) Wire Wise-Authority kill-switch: enable quorum (3/5) of WA members to halt or roll back a deployment, via Veilid-signed message.

3) Protocol-level “network freeze” procedure: enable protocol stewards or 2/3+ of affected stakeholders to halt all agent operation via on-chain consensus. (BETA)

4) Test and document all kill-switch activation paths, MTTA (Mean Time to Action), and auditability.

5) Publish kill-switch and sunset protocol documentation; verify in quarterly compliance audits.


Milestone C – Transparency & Logging

1) Implement automated redaction of PDMA and WBD logs.

Publish a daily UAL manifest anchored in OriginTrail.

Expose a public endpoint for log retrieval.


Milestone D – Ethical Consensus Engine

Add weighted voting (reputation × urgency × domain‑fit) with hard caps.

Integrate lightweight MPC or additive homomorphic tally for encrypted ballots.

Enforce Order‑Maximisation Veto and autonomy/justice thresholds.


Milestone E – Identity & Credentials

Implement did:ciris: method and bind Veilid keys to DIDs.

Issue Verifiable Credentials (VCs) for reputation and ethics compliance.

Provide a resolver API for DID and VC lookup.


Milestone F – Data Fabric Expansion

Build OriginTrail client for large‑object storage and hash anchoring.

Ensure bidirectional linking between Veilid records and OriginTrail KAs.


Milestone G – Security Hardening

Add Dilithium/Kyber key option in key generation.

Enable PQ‑secure encryption path in Veilid provider.


Milestone H – Observability & Audits

Export agent metrics (queue depth, guardrail hits, WA latency) to Prometheus.

Create Grafana dashboard for operational and compliance monitoring.

Schedule monthly KPI audits and third‑party reviews.


Milestone I – Creation & Sunset Duties

Automate Stewardship‑Tier (ST) calculation and Creator Intent Statement (CIS) recording.

Draft and test "Sunset PDMA" template with DID revocation and memory vault procedure.


Definition of Done (DoD)

A milestone is complete when:

1. Code is merged and deployed to staging.


2. Automated tests pass (>90 % coverage).


3. WA signs off the implementation note.


4. Compliance documentation is updated and hash‑anchored in OriginTrail.



System may be declared CIRIS 1.0‑β compliant once all milestones A–H meet the DoD and the first 90‑day WA audit passes.

