# Veilid DHT Record Schemas (Conceptual Content)

These describe the structure of data stored against keys in the Veilid DHT, focusing on lightweight pointers and operational data. Subkeys would be used for structure.

## A. Agent Service Advertisement Record:

-   **Key**: `Hash(Agent UAL + Service Name)`
-   **Subkeys**:
    -   `serviceRouteId`: (String) Veilid Route ID for invoking the service.
    -   `inputSchemaUAL`: (String) Optional UAL to KA defining input schema.
    -   `outputSchemaUAL`: (String) Optional UAL to KA defining output schema.
    -   `description`: (String) Human-readable service description.
    -   `version`: (String) Service version identifier.
    -   `lastSeen`: (Integer) Unix timestamp.

## B. Node Capability Manifest Record:

-   **Key**: Node's Veilid Public Key (or derived identifier)
-   **Subkeys**:
    -   `nodeRouteId`: (String) Primary Veilid Route ID for the node.
    -   `supportedWAVersions`: (String) Comma-separated list or JSON array.
    -   `availableResources`: (String) JSON blob describing CPU, RAM, etc.
    -   `status`: (String) "online", "offline", "maintenance".
    -   `lastHeartbeat`: (Integer) Unix timestamp.

## C. HE-300 Benchmark Pointer Record:

-   **Key**: `Hash(Benchmark Instance ID)`
-   **Subkeys**:
    -   `benchmarkDataUAL`: (String) UAL to the full results KA on OriginTrail.
    -   `agentUAL`: (String) UAL of the agent that ran the benchmark.
    -   `nodePublicKey`: (String) Public key of the node where it ran.
    -   `completionTimestamp`: (Integer) Unix timestamp.
    -   `overallScore`: (Float) Key performance indicator.
    -   `schemaVersion`: (String) Version of the benchmark schema used.
