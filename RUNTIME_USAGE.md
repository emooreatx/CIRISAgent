# CLI Runtime Usage Guide

## Starting the CLI Runtime

```bash
python main.py --mode cli --profile default --no-interactive
```
Pass `--mock-llm` to run entirely offline using the bundled mock service.

## Available Commands

- Type messages to interact with the agent
- Use `exit`, `quit`, or `bye` to shutdown
- Special commands:
  - `/defer` - View pending deferrals
  - `/tools` - List available tools
  - `/status` - Show agent status

## CLI Tool Examples

```
>>> list_files path=/home/user/documents
>>> read_file path=/home/user/documents/example.txt
>>> shell_command cmd="ls -la"
```

# API Runtime Usage Guide

## Starting the API Runtime

```bash
python main.py --mode api --profile default --host 0.0.0.0 --port 8080
```

## API Endpoints

### POST /v1/messages
Send a message to the agent:
```json
{
  "content": "Hello agent",
  "author_id": "user123",
  "author_name": "John Doe",
  "channel_id": "api"
}
```

### GET /v1/status
Get agent status and pending responses

### POST /v1/tools/{tool_name}
Execute a tool:
```json
{
  "args": {
    "param1": "value1"
  }
}
```

