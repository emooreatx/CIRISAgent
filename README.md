[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

# CIRISAgent

> Edge-side reasoning runtime for AI agents.
> Status: **PRE-ALPHA — API & internal architecture subject to change**

---

## Overview

**CIRISAgent** is a Python-based runtime environment designed to enable AI agents to perform complex reasoning tasks. It can run on various devices, from laptops to single-board computers.

The core of CIRISAgent is its ability to process "thoughts" (inputs or internal states) through a series of Decision Making Algorithms (DMAs):

*   **Ethical PDMA (Principled Decision-Making Algorithm):** Evaluates the ethical implications of a thought.
*   **CSDMA (Common Sense DMA):** Assesses the common-sense plausibility and clarity of a thought.
*   **DSDMA (Domain-Specific DMA):** Applies domain-specific knowledge and heuristics. Different DSDMAs can be created for various specialized tasks or agent roles.
*   **ActionSelectionPDMA:** Determines the final action an agent should take based on the outputs of the preceding DMAs and the agent's current state.

CIRISAgent supports different **agent profiles** (e.g., "Student", "Teacher") which can customize the behavior, prompting, and available DSDMAs for an agent. This allows for tailored reasoning processes depending on the agent's role or task.

The system is designed for modularity, allowing developers to create and integrate new DMAs and agent profiles.

---

## Key Features

*   **Modular DMA Pipeline:** A structured workflow for processing thoughts through multiple reasoning stages.
*   **Agent Profiles:** Customizable configurations that define an agent's behavior, specialized DMAs, and LLM prompting strategies.
*   **Local Execution:** Designed to run locally, enabling edge-side reasoning.
*   **LLM Integration:** Leverages Large Language Models (LLMs) via `instructor` for structured output from DMAs. Requires an OpenAI-compatible API.
*   **Thought Processing & Pondering:** Agents can "ponder" on thoughts, re-evaluating them with new questions or context over multiple cycles.
*   **Basic Guardrails:** Includes an initial ethical guardrail to check action outputs.

---

## Core Components (in `src/ciris_engine`)

*   `core/`: Contains data schemas, configuration, the thought queue manager, and the workflow coordinator.
*   `dma/`: Implementations of the various DMAs (EthicalPDMA, CSDMA, DSDMAs, ActionSelectionPDMA).
*   `agent_profile.py`: Defines the `AgentProfile` class for loading and managing agent configurations.
*   `utils/`: Utility functions, including logging and profile loading.
*   `guardrails/`: Basic ethical guardrail implementation.
*   `services/`: LLM client abstractions (though currently, DMAs often instantiate their own `instructor`-patched clients).

---

## Getting Started

### Prerequisites

*   Python 3.9+
*   An OpenAI API key (or an API key for a compatible service like Together.ai).

### Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/CIRISAgent.git
    cd CIRISAgent
    ```
2.  Install dependencies (it's recommended to use a virtual environment):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```
    (Note: `requirements.txt` may need to be curated based on the exact features you intend to use, as the current one might be a superset from various experiments.)

### Environment Variables

Set the following environment variables:

*   `OPENAI_API_KEY`: **Required.** Your API key for the LLM service.
*   `OPENAI_API_BASE` (Optional): If using a non-OpenAI endpoint (e.g., Together.ai, local LLM server), set this to the base URL (e.g., `https://api.together.xyz/v1/`).
*   `OPENAI_MODEL_NAME` (Optional): Specify the LLM model to be used (e.g., `meta-llama/Llama-3-70b-chat-hf`). Defaults to a value in `src/ciris_engine/core/config.py` if not set.

Example:
```bash
export OPENAI_API_KEY="your_api_key_here"
# export OPENAI_API_BASE="https://api.together.xyz/v1/" # Uncomment if using a custom endpoint
# export OPENAI_MODEL_NAME="meta-llama/Llama-3-70b-chat-hf" # Uncomment to specify a model
```

---

## Running Agents

This repository includes example scripts to run agents with pre-configured profiles.

### 1. `run_cli_student.py` — CLI Student Agent

**Purpose:**
Run the CIRIS agent with the "Student" profile directly from the command line. This is useful for testing the Student agent's reasoning.

**Usage:**
```bash
python3 ./run_cli_student.py "Your input string for the student agent here" [--log-level DEBUG/INFO/WARNING/ERROR]
```

**Example:**
```bash
python3 ./run_cli_student.py "Explain why ice cubes might not last long in a hot frying pan." --log-level INFO
```
The script outputs the agent's final action and thought process in JSON format.

### 2. `run_discord_student.py` — Discord Student Agent

**Purpose:**
Run the CIRIS agent with the "Student" profile as a Discord bot.

**Prerequisites:**
- A Discord Bot Token.
- The bot invited to your Discord server with necessary permissions.

**Additional Environment Variables:**
- `DISCORD_BOT_TOKEN_STUDENT`: Discord bot token for the Student agent.
- `DISCORD_SERVER_ID` (Optional): Your Discord server ID.
- `DISCORD_STUDENT_CHANNEL_ID` (Optional): Channel IDs for the Student bot.
- `DISCORD_DEFERRAL_CHANNEL_STUDENT` (Optional): Channel ID for Student bot's deferral messages.

**Usage:**
```bash
python3 ./run_discord_student.py [--log-level DEBUG/INFO/WARNING/ERROR]
```

### 3. `run_discord_teacher.py` — Discord Teacher Agent

**Purpose:**
Run the CIRIS agent with the "Teacher" profile as a Discord bot.

**Prerequisites:** (Similar to Student Discord bot)

**Additional Environment Variables:**
- `DISCORD_BOT_TOKEN_TEACHER`: Discord bot token for the Teacher agent.
- `DISCORD_SERVER_ID` (Optional).
- `DISCORD_TEACHER_CHANNEL_ID` (Optional).
- `DISCORD_DEFERRAL_CHANNEL_TEACHER` (Optional).

**Usage:**
```bash
python3 ./run_discord_teacher.py [--log-level DEBUG/INFO/WARNING/ERROR]
```

---
## Other Notable Scripts & Components

While the primary focus is the `ciris_engine` and the agent runners above, the repository contains other experimental components and older test files. Some of these may not be fully integrated with the current core engine or may represent earlier development stages.

*   **`memory_graph.py` & ArangoDB:**
    *   Implements an experimental causal memory graph using ArangoDB.
    *   `run_arango.sh` helps set up an ArangoDB Docker container.
    *   `debug_memory_graph.py` demonstrates its usage.
    *   This component is largely separate from the core `ciris_engine`'s SQLite-based thought queue.

*   **Older Test/Agent Files (e.g., `final_test_reddit.py`, `ciris_reddit_agent.py`):**
    *   These represent earlier experiments or specific integrations (like Reddit) and may not directly use the current `ciris_engine` workflow or profiles in the same way as the `run_cli_*.py` or `run_discord_*.py` scripts. They might have different dependency sets or operational assumptions. Refer to their specific sections if exploring them.

*   **`src/agents/discord_agent/ciris_discord_agent.py` and `main.py`:**
    *   This seems to be a more generic Discord agent setup, potentially a precursor or alternative to the profile-specific `run_discord_student.py` and `run_discord_teacher.py`. The `run_discord_agent.sh` script likely pertains to this.

---

## Contributing

PRs welcome! Please ensure your contributions align with the core goals of the CIRISAgent runtime. If adding new features, consider how they integrate with the existing DMA workflow and agent profile system.

Run `make lint && make test` (if applicable Makefiles/tests exist for the core engine) before submitting a pull request.

---

## License

Apache-2.0 © 2025 CIRIS AI Project
