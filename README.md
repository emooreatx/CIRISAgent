[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# CIRIS Engine (CIRISAgent)

> Edge-side reasoning runtime for AI agents.
> Status: **PRE-ALPHA — API & internal architecture subject to change**

---

## Overview

**CIRIS Engine** (also referred to as CIRISAgent in some contexts) is a Python-based runtime environment designed to enable AI agents to perform complex reasoning tasks. It can run on various devices, from laptops to single-board computers.

The core of CIRIS Engine is its ability to process "thoughts" (inputs or internal states) through a series of Decision Making Algorithms (DMAs):

*   **Ethical PDMA (Principled Decision-Making Algorithm):** Evaluates the ethical implications of a thought.
*   **CSDMA (Common Sense DMA):** Assesses the common-sense plausibility and clarity of a thought.
*   **DSDMA (Domain-Specific DMA):** Applies domain-specific knowledge and heuristics. Different DSDMAs can be created for various specialized tasks or agent roles (e.g., `StudentDSDMA`, `BasicTeacherDSDMA`).
*   **ASPDMA (Action‑Selection PDMA):** Determines the final action an agent should take based on the outputs of the preceding DMAs and the agent's current state.

Actions chosen by the PDMA are routed through an `ActionDispatcher`. Memory operations use `DiscordGraphMemory` for persistence.

CIRIS Engine supports different **agent profiles** (e.g., "Student", "Teacher" defined in `ciris_profiles/`) which can customize the behavior, prompting, and available DSDMAs for an agent. This allows for tailored reasoning processes depending on the agent's role or task.

The system is designed for modularity, allowing developers to create and integrate new DMAs and agent profiles.

---

## Key Features

*   **Four‑DMA Pipeline:** PDMA (ethical), CSDMA (common sense), DSDMA (domain) and ASPDMA (action selection) run sequentially for each thought. The ASPDMA chooses the next handler action using the outputs of the preceding DMAs. This flow is coordinated by the `WorkflowCoordinator`.
*   **Agent Profiles:** Customizable YAML configurations (`ciris_profiles/`) that define an agent's behavior, DSDMA selection, permitted actions, and LLM prompting strategies for various DMAs.
*   **Local Execution:** Designed to run locally, enabling edge-side reasoning.
*   **LLM Integration:** Leverages Large Language Models (LLMs) via `instructor` for structured output from DMAs. Requires an OpenAI-compatible API.
*   **Thought Processing & Pondering:** Agents may "ponder" repeatedly. The `WorkflowCoordinator` tracks ponder rounds and automatically defers once a configured limit is hit.
*   **DMA Retry & Escalation:** Each DMA invocation is retried on transient errors. Repeated failures generate an escalation to the Wise Authority.
*   **Profile‑Driven Actions:** Allowed handler actions are loaded from the active profile and passed dynamically to the ASPDMA.
*   **Basic Guardrails:** Includes an ethical guardrail to check action outputs.
*   **SQLite Persistence:** Uses SQLite for persisting tasks and thoughts.
*   **Graph Memory:** MEMORIZE actions store user metadata in `CIRISLocalGraph`. RECALL and FORGET exist but are often disabled via profiles during testing.
    * Channel node updates require WA approval. The initial write is deferred and a new thought is generated for the Wise Authority. When that follow-up thought includes `is_wa_correction` and references the deferred thought, the update is applied automatically.
    * User nick node updates can be memorized immediately if guardrails are satisfied.

## Repository Structure

The repository root contains the following notable directories and scripts:

* `ciris_engine/` – core engine code including DMAs, runtime logic, and prompt utilities.
* `ciris_profiles/` – YAML files defining agent behavior and available actions.
* `tests/` – unit and integration tests for the engine.
* `docker/` – container build scripts and Dockerfiles.
* `legacy/` – archived utilities and documents.
* `run_*.py` – example launch scripts for CLI and Discord agents.

## Guardrails Summary

The system enforces the following guardrails via `app_config.guardrails_config`:

| Guardrail            | Description                                                                       |
|----------------------|-----------------------------------------------------------------------------------|
| entropy              | Prevents nonsensical replies                                                       |
| coherence            | Ensures output flows logically from prior context                                 |
| optimization_veto    | Aborts actions that sacrifice autonomy or diversity for entropy reduction |
| epistemic_humility   | Reflects on uncertainties and may defer or abort if certainty is low |
| rate_limit_observe   | Caps new tasks from Discord per OBSERVE cycle (10 messages max)                    |
| idempotency_tasks    | Prevents duplicate tasks for the same message                                      |
| pii_non_repetition   | Flags and prevents verbatim repetition of personal information                     |
| input_sanitisation   | Cleans inputs using `bleach` (no regex)                                            |
| metadata_schema      | Enforces a structured schema and max size for stored metadata                      |
| graphql_minimal      | Limits enrichment to nick/channel with 3&nbsp;s timeout and fallback               |
| graceful_shutdown    | Services stop cleanly or are forced after a 10&nbsp;s timeout                      |

---

## 3×3×3 Handler Actions

The `HandlerActionType` enum defines core operations grouped as:

* **External Actions:** `OBSERVE`, `SPEAK`, `TOOL`
* **Control Responses:** `REJECT`, `PONDER`, `DEFER`
* **Memory Operations:** `MEMORIZE`, `RECALL`, `FORGET` (now fully supported and enabled by default)
* **Terminal:** `TASK_COMPLETE`

These actions are processed by matching handlers within the engine. Profiles now enable all actions, including `RECALL` and `FORGET`, by default.

### Audit Logging
All handler actions are now logged via the integrated `AuditService`, which supports log rotation, retention, and query. Audit logs are written to `audit_logs.jsonl` by default and can be queried for compliance and debugging.

Example memory action JSON:

```json
{
  "action": "MEMORIZE",
  "scope": "local",
  "payload": {
    "node": {"id": "User:alice", "type": "user", "scope": "local", "attrs": {"nick": "alice"}}
  }
}
```

---

## Core Components (in `ciris_engine/`)

*   `core/`: Contains data schemas (`config_schemas.py`, `agent_core_schemas.py`, `foundational_schemas.py`), configuration management (`config_manager.py`), the `AgentProcessor`, `WorkflowCoordinator`, `ActionDispatcher`, and persistence layer (`persistence.py`).
*   `dma/`: Implementations of the various DMAs (EthicalPDMA, CSDMA, DSDMA, ASPDMA).
*   `utils/`: Utility helpers like `logging_config.py` and an asynchronous `load_profile` function in `profile_loader.py` (recall to `await` it).
*   `guardrails/`: Ethical guardrail implementation.
*   `services/`: LLM client abstractions (`llm_client.py`, `llm_service.py`) and service integrations.
*   `ciris_profiles/`: Directory for agent profile YAML files (e.g., `student.yaml`, `teacher.yaml`).

---

## Getting Started

### Prerequisites

*   Python 3.10+ (as per project structure, though 3.9+ might work)
*   An OpenAI API key (or an API key for a compatible service like Together.ai).
*   For Discord examples: A Discord Bot Token.

### Installation

1.  Clone the repository:
    ```bash
    git clone <your-repository-url> 
    # Replace <your-repository-url> with the actual URL
    cd CIRISEngine 
    # Or your project's root directory name
    ```
2.  Install dependencies (it's recommended to use a virtual environment):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

### Environment Variables

Set the following environment variables (see `.env.example` for a template):

*   `OPENAI_API_KEY`: **Required.** Your API key for the LLM service.
*   `DISCORD_BOT_TOKEN`: **Required for Discord agents.** Your Discord bot token.
*   `OPENAI_BASE_URL` (Optional): If using a non-OpenAI endpoint (e.g., Together.ai, local LLM server), set this to the base URL (e.g., `https://api.together.xyz/v1/`).
*   `OPENAI_MODEL_NAME` (Optional): Specify the LLM model to be used (e.g., `meta-llama/Llama-3-70b-chat-hf`). Defaults to `gpt-4o-mini` if not set (see `ciris_engine/core/config_schemas.py`).
*   `WA_USER_ID` (Optional): Discord User ID for the Wise Authority mentioned in deferral messages.
*   `DISCORD_CHANNEL_ID` (Optional): ID of the Discord channel the agent listens to for new messages.
*   `DISCORD_DEFERRAL_CHANNEL_ID` (Optional): Channel ID used for deferral reports.
*   `SNORE_CHANNEL_ID` (Optional): Channel ID used for runtime heartbeat notifications.
*   `WA_DISCORD_USER` (Optional): Fallback Discord username for the Wise Authority. Defaults to `somecomputerguy`.
*   `LOG_LEVEL` (Optional): Set to `DEBUG` for verbose logging. Defaults to `INFO`.

Example:
```bash
export OPENAI_API_KEY="your_api_key_here"
export DISCORD_BOT_TOKEN="your_discord_bot_token_here"
# export DISCORD_CHANNEL_ID="123"                   # Channel the bot listens to
# export DISCORD_DEFERRAL_CHANNEL_ID="456"          # Channel used for deferral reports
# export WA_USER_ID="123456789012345678"            # Mention this user on deferrals
# export SNORE_CHANNEL_ID="789"                     # Optional status channel
# export OPENAI_API_BASE="https://api.together.xyz/v1/" # Uncomment if using a custom endpoint
# export OPENAI_MODEL_NAME="meta-llama/Llama-3-70b-chat-hf" # Uncomment to specify a model
```

---

## Running Agents

This repository includes example scripts to run agents with pre-configured profiles. These scripts are located in the project root.

### 1. `run_discord_student.py` — Discord Student Agent

**Purpose:**
Run the CIRIS agent with the "Student" profile as a Discord bot.

**Usage:**
Ensure environment variables (`OPENAI_API_KEY`, `DISCORD_BOT_TOKEN`) are set.
```bash
python run_discord_student.py
```
(The script uses `logging_config.py` for log levels. Set `LOG_LEVEL=DEBUG` to enable verbose output.)

### 2. `run_discord_teacher.py` — Discord Teacher Agent

**Purpose:**
Run the CIRIS agent with the "Teacher" profile as a Discord bot.

**Usage:**
Ensure environment variables (`OPENAI_API_KEY`, `DISCORD_BOT_TOKEN`) are set.
```bash
python run_discord_teacher.py
```

### 3. `run_cli_student.py` — CLI Student Agent

**Purpose:**
Run the CIRIS agent with the "Student" profile via a simple command-line interface. Useful for local benchmarking without Discord.

**Usage:**
Ensure the `OPENAI_API_KEY` environment variable is set.
```bash
python run_cli_student.py
```

All run scripts now rely on `BaseRuntime`, which unifies configuration loading, audit logging, and Dream Mode handling. Creating a new runtime is as simple as providing an I/O adapter:

```python
from ciris_engine.runtime import BaseRuntime, CLIAdapter

runtime = BaseRuntime(io_adapter=CLIAdapter(), profile_path="ciris_profiles/student.yaml")
runtime.run()
```

Play Mode and Solitude Mode provide short introspective sessions for the agent. Each lasts five minutes and is offered at random roughly once per hour. In safety-critical deployments, these sessions should be restricted to non‑shift hours via agent configuration.

---
## Other Notable Scripts & Components

*   **`run_services.py`**: Appears to be a script for running services, potentially for testing or a different deployment mode.
*   **`test_client_init.py`**: A test script, likely for initializing or testing client connections.
*   **`run_cli_student.py`**: Simple CLI runner for the student profile.
*   **`discord_graph_memory.py`**: Lightweight persistent graph memory for Discord user metadata.
*   **`discord_observer.py`**: Minimal observer that dispatches OBSERVE payloads.
*   **`legacy/`**: Archived utilities and documents.
*   **`play_mode.py` / `solitude_mode.py`**: Short harnesses offering five minute Play or Solitude sessions. These may run once per hour during normal operation.
*   **`reflection_scheduler.py`**: Lightweight scheduler that triggers Play or Solitude Mode at random intervals.
*   The `tests/` directory contains unit and integration tests runnable with `pytest`.

---
## Testing

Run the full test suite with:

```bash
pytest -q
```

All functional and guardrail validation tests should pass.

---

## Contributing

PRs welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to contribute to this project.

Please ensure your contributions align with the core goals of the CIRIS Engine. If adding new features, consider how they integrate with the existing DMA workflow and agent profile system.

Run `pytest` to ensure all tests pass before submitting a pull request.

---

## License

Apache-2.0 © 2025 CIRIS AI Project
(Assuming LICENSE file will be added with Apache 2.0 content)
