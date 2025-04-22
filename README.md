# CIRIS Agent Test Suite

This repository demonstrates a dual-mode testing framework for AI governance agents, supporting both **offline unit tests** (no API required) and **integration tests** with the OpenAI API. It includes cryptographic logging, ethical reasoning, and tamper-evident audit trails.

---

## File Overview

| File                    | Purpose                                                                                 |
|-------------------------|-----------------------------------------------------------------------------------------|
| `final_test_reddit.py`  | **Offline unit tests:** test cryptography, logging, and logic without any API calls.    |
| `test_reddit.py`        | **Integration tests:** run CIRIS agent with OpenAI API for live model-based scenarios.  |
| `reasoning_agent.py`    | AutoGen ReasoningAgent extensions for ethical/PDMA logic.                               |
| `ciris_reddit_agent.py` | CIRIS Reddit agent implementation (governance logic and Reddit integration).            |

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

## Example: Running the Suite

### 1. Offline/Unit Tests
export CIRIS_ENCRYPTION_KEY="testkey"
python -m pytest final_test_reddit.py

text

### 2. OpenAI Integration

export OPENAI_API_KEY="sk-your-openai-key"
export CIRIS_ENCRYPTION_KEY="testkey"
python test_reddit.py

text

---

## Requirements Files

**For offline tests (`final_test_reddit.py`):**
cryptography
pytest

text

**For API tests (`test_reddit.py`, `ciris_reddit_agent.py`):**

autogen
openai
cryptography
praw

text

---

## Notes

- **Do not include built-in modules** (like `os`, `hashlib`, etc.) in your `requirements.txt`.
- **Never share your real OpenAI API key** in public code or logs.
- All logs are encrypted and hash-chained for tamper evidence.
- The CIRIS agent's logic can be extended or integrated into other governance systems.

---

## References

- [OpenAI Python SDK](https://pypi.org/project/openai/)
- [AutoGen by Microsoft](https://github.com/microsoft/autogen)
- [PRAW (Python Reddit API Wrapper)](https://praw.readthedocs.io/)
- [cryptography](https://cryptography.io/en/latest/)