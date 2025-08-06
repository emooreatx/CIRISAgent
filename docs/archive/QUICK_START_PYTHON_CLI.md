# CIRIS Quick Start Guide

**In 2 minutes, you'll have:** A running AI agent that explains its decisions, asks for permission before taking actions, and maintains a consistent identity across sessions.

## Prerequisites

- Python 3.11+
- Git
- OpenAI API key (or use `--mock-llm` for testing)

## 1. Clone and Install (30 seconds)

```bash
git clone https://github.com/yourusername/CIRISAgent.git
cd CIRISAgent
pip install -r requirements.txt
```

## 2. First Run (30 seconds)

### Option A: CLI Mode (Interactive Terminal)
```bash
# With real LLM
export OPENAI_API_KEY="your-key-here"
python main.py --adapter cli --template datum

# With mock LLM (for testing)
python main.py --adapter cli --template datum --mock-llm
```

### Option B: API Mode (REST API)
```bash
# Start the API server
python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080

# In another terminal, send a message
curl -X POST http://localhost:8080/v1/message \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello CIRIS, what can you do?"}'
```

### Option C: Discord Mode (Bot)
```bash
# Set up Discord bot token
export DISCORD_BOT_TOKEN="your-bot-token"
python main.py --adapter discord --template datum
```

## 3. What Happens on First Run (1 minute)

1. **Root Wise Authority Creation**: You'll be asked to confirm creation of the "root" authority that approves the agent's initial identity
2. **Identity Formation**: The agent will introduce itself based on the template you chose
3. **Exit Question**: When you're done, the agent will ask if you want to exit - this is the Wise Authority system in action

Example first interaction:
```
You: Hello!
CIRIS: Hello! I'm CIRIS, an AI agent designed to assist while explaining my reasoning.
I operate under a Wise Authority system that ensures I seek approval for significant
actions. How may I help you today?

You: exit
CIRIS: I need permission to shut down. This action requires approval from the Wise
Authority system. Do you approve this shutdown? (yes/no)
You: yes
CIRIS: Shutdown approved. Goodbye!
```

## Key Commands to Try

```bash
# See the agent's reasoning process
You: Why do you ask for permission?

# Test the memory system
You: Remember that my favorite color is blue
You: What's my favorite color?

# See available tools (in CLI mode)
You: What tools do you have available?
```

## Docker Quick Start (Alternative)

```bash
# Using docker-compose
docker-compose -f docker-compose-api-mock.yml up -d

# Check it's running
curl http://localhost:8080/v1/health
```

## What Makes CIRIS Different?

- **Wise Authority System**: The agent asks for permission before significant actions
- **Transparent Reasoning**: Every decision is explained and logged
- **Persistent Identity**: The agent maintains its identity and memories across sessions
- **No Hidden Behavior**: All capabilities and limitations are explicit

## Next Steps

- **Understand the Philosophy**: Read [WISE_AUTHORITIES.md](./WISE_AUTHORITIES.md)
- **Explore the Architecture**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Build Custom Agents**: Check [TEMPLATES.md](./TEMPLATES.md)
- **Deploy to Production**: Follow [DEPLOYMENT.md](./DEPLOYMENT.md)

## Troubleshooting

**"No module named 'ciris_engine'"**: Make sure you're in the CIRISAgent directory

**"OpenAI API key not found"**: Either set `OPENAI_API_KEY` or use `--mock-llm`

**"Port already in use"**: Change the port with `--port 8081`

## Get Help

- GitHub Issues: [Report bugs or ask questions](https://github.com/yourusername/CIRISAgent/issues)
- Documentation: [Full docs](./README.md)
