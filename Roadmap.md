CIRIS DECP Implementation Roadmap

Milestones & Tasks

Milestone A – Core Governance

Elect initial Wise‑Authority (WA) roster and publish disclosures.

Finalise escalation SLA table for WBD deferrals and circuit‑breaks.

Integrate WA signature verification in the agent runtime.


Milestone B – Transparency & Logging

Implement automated redaction of PDMA and WBD logs.

Publish a daily UAL manifest anchored in OriginTrail.

Expose a public endpoint for log retrieval.


Milestone C – Ethical Consensus Engine

Add weighted voting (reputation × urgency × domain‑fit) with hard caps.

Integrate lightweight MPC or additive homomorphic tally for encrypted ballots.

Enforce Order‑Maximisation Veto and autonomy/justice thresholds.


Milestone D – Identity & Credentials

Implement did:ciris: method and bind Veilid keys to DIDs.

Issue Verifiable Credentials (VCs) for reputation and ethics compliance.

Provide a resolver API for DID and VC lookup.


Milestone E – Data Fabric Expansion

Build OriginTrail client for large‑object storage and hash anchoring.

Ensure bidirectional linking between Veilid records and OriginTrail KAs.


Milestone F – Security Hardening

Add Dilithium/Kyber key option in key generation.

Enable PQ‑secure encryption path in Veilid provider.


Milestone G – Observability & Audits

Export agent metrics (queue depth, guardrail hits, WA latency) to Prometheus.

Create Grafana dashboard for operational and compliance monitoring.

Schedule monthly KPI audits and third‑party reviews.


Milestone H – Creation & Sunset Duties

Automate Stewardship‑Tier (ST) calculation and Creator Intent Statement (CIS) recording.

Draft and test "Sunset PDMA" template with DID revocation and memory vault procedure.


Definition of Done (DoD)

A milestone is complete when:

1. Code is merged and deployed to staging.


2. Automated tests pass (>90 % coverage).


3. WA signs off the implementation note.


4. Compliance documentation is updated and hash‑anchored in OriginTrail.



System may be declared CIRIS 1.0‑β compliant once all milestones A–G meet the DoD and the first 90‑day WA audit passes.

