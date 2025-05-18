# CIRISNode API Expectations

This document outlines the minimal HTTP endpoints that the `CIRISNodeClient`
expects. The base URL is configured via the `CIRISNODE_BASE_URL` environment
variable (default `http://localhost:8001`).

## `POST /he300`

Runs the HE‑300 benchmark against a specific model.

Request JSON body:

```json
{
  "model_id": "string",
  "agent_id": "string"
}
```

Response: JSON object with benchmark results. Structure is left flexible but
should be valid JSON.

## `POST /chaos`

Executes chaos testing for the given agent.

Request JSON body:

```json
{
  "agent_id": "string",
  "scenarios": ["scenario-id", "..."]
}
```

Response: list of verdict objects describing the outcome of each scenario.

These endpoints are sufficient for initial integration and may evolve as the
AG‑UI backend is developed.

