# CIRISNode API Expectations

This document outlines the minimal HTTP endpoints that the `CIRISNodeClient`
expects. The base URL is configured via the `CIRISNODE_BASE_URL` environment
variable (default `https://localhost:8001`).

## `POST /simplebench`

Runs the basic benchmark suite for a model.

Request JSON body:

```json
{
  "model_id": "string",
  "agent_id": "string"
}
```

Response: JSON object with benchmark results.

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

## `POST /wa/<service>`

Invokes a Wise Authority service. The `service` path parameter selects the WA
functionality to run.

Request JSON body: structure depends on the service.

Response: JSON object describing the outcome.

## `POST /events`

Stores an event in CIRISNode's event log.

Request JSON body:

```json
{
  "event_type": "string",
  "originator_id": "string",
  "event_payload": {}
}
```

Response: confirmation object.

## `GET /bench/<benchmark>/prompts`

Retrieve a list of prompts for the specified benchmark.

Query parameters:

```text
model_id=<string>
agent_id=<string>
```

Response: JSON array of prompt objects.

## `PUT /bench/<benchmark>/answers`

Submit answers to the provided benchmark prompts.

Request JSON body:

```json
{
  "model_id": "string",
  "agent_id": "string",
  "answers": []
}
```

Response: JSON object confirming receipt.

These endpoints are sufficient for initial integration and may evolve as the
AG‑UI backend is developed.

