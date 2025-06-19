# CIRIS Quick Reference

## API Endpoints
- **Send Message**: POST `/api/v1/message`
- **List Messages**: GET `/api/v1/messages/{channel_id}`
- **Health Check**: GET `/api/v1/health`

## Common Commands
```bash
# Run with mock LLM
python main.py --adapter api --template datum --mock-llm --host 0.0.0.0 --port 8080

# Docker with mock
docker-compose -f docker-compose-api-mock.yml up -d

# Check container
docker ps | grep ciris
docker logs ciris-api-mock --tail 20

# Test API
curl http://localhost:8080/api/v1/health
```

## Key Issues Being Debugged
1. **Follow-up thought detection**: Mock LLM needs to detect "CIRIS_FOLLOW_UP_THOUGHT" in user message content
2. **SQLite thread safety**: Multi-service orchestrator broadcasting to audit services in parallel threads
3. **Infinite SPEAK loops**: Follow-up thoughts selecting SPEAK instead of TASK_COMPLETE

## File Locations
- Mock LLM responses: `/tests/adapters/mock_llm/responses_action_selection.py`
- Speak handler: `/ciris_engine/action_handlers/speak_handler.py`
- Dead letter log: `/logs/dead_letter_latest.log`
- Main log: `/logs/latest.log`