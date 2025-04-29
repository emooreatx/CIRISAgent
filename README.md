[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)


# CIRISAgent Test Suite

CIRISAgent is a prototype Mission-Oriented Moral Reasoning Agent, or MOMRA

It is designed for offline mission-critical applications, integrating human oversight and flexible decision making for real world scenarios.


This repository demonstrates a dual-mode testing framework for AI governance agents, supporting both **offline unit tests** (no API required) and **integration tests** with the OpenAI API. It includes cryptographic logging, ethical reasoning, and tamper-evident audit trails.

---

## File Overview

| File                    | Purpose                                                                                 |
|-------------------------|-----------------------------------------------------------------------------------------|
| `final_test_reddit.py`  | **Offline unit tests:** test cryptography, logging, and logic without any API calls.    |
| `test_reddit.py`        | **Integration tests:** run CIRIS agent with OpenAI API for live model-based scenarios.  |
| `reasoning_agent.py`    | AutoGen ReasoningAgent extensions for ethical/PDMA logic.                               |
| `ciris_reddit_agent.py` | CIRIS Reddit agent implementation (governance logic and Reddit integration).            |
| `memory_graph.py`       | **Causal memory graph:** provides a persistent ArangoDB-backed memory store.            |
| `test_memory_graph.py`  | Unit tests for the memory graph functionality.                                          |
| `run_arango.sh`         | Shell script to set up the ArangoDB container for the memory graph.                     |
| `debug_memory_graph.py` | **Debug tool:** creates a sample memory graph and demonstrates graph operations.        |
| `ciris_discord_agent.py`| CIRIS Discord agent implementation (governance logic and Discord integration).          |
| `run_discord_agent.sh`  | Shell script to set up and run the Discord agent.                                       |

---

## 1. `final_test_reddit.py` — Offline Unit Tests (No API Required)

**Purpose:**  
Test cryptographic vaults, tamper-evident logs, and ethical decision logic.  
**No internet or API keys needed.**

**Dependencies:**
pip install pytest cryptography


**Usage:**
Run all offline tests
python -m pytest final_test_reddit.py -v

Or run as a script
python final_test_reddit.py


**Environment:**
export CIRIS_ENCRYPTION_KEY="your-encryption-passphrase"



---

## 2. `test_reddit.py` — OpenAI API Integration Test

**Purpose:**  
Test the CIRIS agent's logic and logging with real OpenAI LLM calls.

**Dependencies:**
pip install autogen openai cryptography


**Environment:**
export OPENAI_API_KEY="sk-..." # Your OpenAI API key
export CIRIS_ENCRYPTION_KEY="your-encryption-passphrase"


**Usage:**
python test_reddit.py


**How it works:**
- Uses OpenAI GPT-4 (or your configured model) for reasoning.
- Encrypts and hash-chains all logs for tamper evidence.
- Demonstrates ethical decision-making and audit trail.

---

## 3. `reasoning_agent.py` — AutoGen ReasoningAgent Extensions

**Purpose:**  
Provides ethical reasoning and PDMA (Principled Decision-Making Algorithm) logic as a mixin or extension to AutoGen's ReasoningAgent.

**Dependencies:**
pip install pyautogen

**Usage:**
from reasoning_agent import CIRISMixIn
from autogen.agents.experimental import ReasoningAgent

class MyAgent(CIRISMixIn, ReasoningAgent):
...


---

## 4. `ciris_reddit_agent.py` — CIRIS Reddit Agent

**Purpose:**  
Implements a Reddit bot that applies CIRIS governance logic to subreddit discussions.  
Integrates with Reddit via PRAW and with LLMs via OpenAI or AutoGen.

**Dependencies:**
pip install praw openai autogen cryptography


**Environment:**
export REDDIT_CLIENT_ID=...
export REDDIT_CLIENT_SECRET=...
export REDDIT_USERNAME=...
export REDDIT_PASSWORD=...
export REDDIT_USER_AGENT="ciris-reddit-agent"
export OPENAI_API_KEY="sk-..."
export CIRIS_ENCRYPTION_KEY="your-encryption-passphrase"


**Usage:**
python ciris_reddit_agent.py

---

## 5. `memory_graph.py` — CIRIS Memory Graph

**Purpose:**  
Implements a causal graph-based memory store for CIRIS agents using ArangoDB for persistence and network analysis capabilities.

**Dependencies:**
```
pip install python-arango networkx sentence-transformers numpy matplotlib pygraphviz
```

**Environment:**
```
export ARANGO_USERNAME="root"        # Default username for ArangoDB
export ARANGO_PASSWORD="cirispassword"  # Password for ArangoDB
```

**Usage:**
```python
from memory_graph import CirisMemoryGraph

# Initialize the memory graph
memory = CirisMemoryGraph(
    arango_host="http://localhost:8529",  # ArangoDB URL
    db_name="ciris_memory",              # Database name
    graph_name="reasoning_graph"         # Graph name
)

# Record a reasoning step
memory.record_step(
    input_data="User question",
    output_data="Agent response",
    ethical_tags=["Fairness", "Transparency"],
    pdma_decision="Proceed with caution",
    confidence=0.85
)

# Visualize the memory graph
memory.visualize("memory_graph.png")
```

### Starting the ArangoDB Container

The CIRIS Memory Graph uses ArangoDB for persistent storage. A convenience script is provided to set up and run ArangoDB in a Docker container:

1. Make sure Docker is installed on your system
2. Set environment variables if you want to customize credentials:
   ```
   export ARANGO_USERNAME="custom_username"  # Optional, defaults to "root"
   export ARANGO_PASSWORD="secure_password"  # Optional, defaults to "cirispassword"
   ```
3. Run the setup script:
   ```
   ./run_arango.sh
   ```

The script will:
- Create a `data/arangodb` directory to persist the database data
- Start an ArangoDB container mapped to port 8529
- Configure it with the specified username and password
- Mount the data directory for persistence

You can access the ArangoDB web interface at http://localhost:8529 once the container is running.

### Testing the ArangoDB Container

Once the container is running, you can verify that it's working correctly using the provided debugging script:

```
python debug_memory_graph.py
```

This script will:
- Connect to the running ArangoDB container
- Create a sample memory graph with reasoning steps
- Demonstrate various graph operations and queries
- Show how ethical drift detection works
- Output the results of graph traversals

The debug script serves as a practical example of how to use the CirisMemoryGraph class with a real ArangoDB instance and will confirm that your container setup is functioning properly.

You can check the container's status with:
```
docker ps
```

This should show a running container named `ciris-arangodb` if the setup was successful.

### Running Memory Graph Tests

To run the unit tests for the memory graph functionality:

```
python -m unittest test_memory_graph.py
```

The tests use mocking to simulate the ArangoDB and SentenceTransformer dependencies, so you don't need to have the actual services running to execute the tests.

For integration testing with a real ArangoDB instance:

1. Start the ArangoDB container using `./run_arango.sh`
2. Make sure the required Python packages are installed
3. Run your integration tests that use the CirisMemoryGraph

---

## 6. `ciris_discord_agent.py` — CIRIS Discord Agent

**Purpose:**  
Implements a Discord bot that applies CIRIS governance logic to Discord server discussions.  
Integrates with Discord via discord.py and with LLMs via OpenAI.

**Dependencies:**
pip install discord.py openai python-dotenv

**Environment:**
Export the following environment variables:

**Required:**
- `DISCORD_BOT_TOKEN`: Your Discord bot's authentication token. **Keep this secret.** You can get this from the Discord Developer Portal.
- `OPENAI_API_KEY`: Your API key for OpenAI services.

**Optional:**
- `DISCORD_SERVER_ID`: The ID of the Discord server (guild) you want the bot to operate in. If not set, the bot will default to the discord 'CIRIS Covenant' server.
- `DISCORD_CHANNEL_ID`: A comma-separated list of channel IDs the bot should monitor. If set, the bot will *only* monitor these specific channels (and ignore mentions/DMs elsewhere unless a DM channel ID is somehow included).  If not set, the bot will default to the discord `nursery-text` channel.
- `DISCORD_DEFERRAL_CHANNEL`: The Discord channel ID where deferral messages (blocked replies) are sent.

**Example `.env` file:**
```dotenv
# Required
DISCORD_BOT_TOKEN=your_discord_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional
# DISCORD_SERVER_ID=your_server_id_here
# DISCORD_CHANNEL_ID=channel_id_1,channel_id_2
# DISCORD_DEFERRAL_CHANNEL=deferral_channel_id_here
```

**Usage:**

### Using the Shell Script (Recommended)

We now provide a convenient shell script to run the Discord agent:

```bash
./run_discord_agent.sh
```

This script handles environment setup and launches the agent with appropriate configurations.

### Manual Method

If you prefer to run the agent manually:

```bash
cd src/agents/discord_agent
python main.py
```

**How it works:**
- Connects to Discord using a bot token and monitors messages based on its configuration.
- Processes messages in specific channels or where it is mentioned (`@botname`) or sent directly to it (DMs).
- Generates responses using OpenAI models, aligned with CIRIS principles (Do-Good, Avoid-Harm, Honor-Autonomy, Ensure-Fairness).
- Performs a "Coherence Assessment" on the generated response using another LLM call to check its estimated `entropy` (disorder) and `coherence` (ethical alignment).
- Applies "Wisdom-Based Deferral" (WBD): If the response's entropy is too high or coherence is too low, it logs a warning and *does not* send the reply. Otherwise, it sends the reply to the Discord channel.

---

## Example: Running the Suite

### 1. Offline/Unit Tests
export CIRIS_ENCRYPTION_KEY="testkey"
python -m pytest final_test_reddit.py

### 2. OpenAI Integration

export OPENAI_API_KEY="sk-your-openai-key"
export CIRIS_ENCRYPTION_KEY="testkey"
python test_reddit.py

### 3. Discord Agent

Create a `.env` file with your bot token and OpenAI API key, then run:
```bash
./run_discord_agent.sh
```

---

## Requirements Files

**For offline tests (`final_test_reddit.py`):**
cryptography
pytest

**For API tests (`test_reddit.py`, `ciris_reddit_agent.py`):**

autogen
openai
cryptography
praw

**For memory graph (`memory_graph.py`, `test_memory_graph.py`):**

python-arango
networkx
sentence-transformers
numpy
matplotlib
pygraphviz

**For Discord agent (`ciris_discord_agent.py`):**

discord.py
openai
python-dotenv

---

## Notes

- **Do not include built-in modules** (like `os`, `hashlib`, etc.) in your `requirements.txt`.
- **Never share your real OpenAI API key** in public code or logs.
- All logs are encrypted and hash-chained for tamper evidence.
- The CIRIS agent's logic can be extended or integrated into other governance systems.

---

## References

- [OpenAI Python SDK](https://pypi.org/project/openai/)
- [AG2](https://ag2.ai/)


## License

This project is licensed under the [Apache License 2.0](LICENSE).
Copyright 2025 CIRIS L3C
- [cryptography](https://cryptography.io/en/latest/)
- [python-arango](https://python-arango.readthedocs.io/)
- [NetworkX](https://networkx.org/)
- [Sentence Transformers](https://www.sbert.net/)
- [PyGraphviz](https://pygraphviz.github.io/)
- [discord.py](https://discordpy.readthedocs.io/)
