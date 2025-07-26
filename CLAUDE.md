# CLAUDE.md - Claude Development Notes

This file contains specific instructions and context for Claude when working on the CIRIS codebase.

## Quick Reference

### Running Locally
```bash
# Manager with OAuth
GOOGLE_CLIENT_ID=xxx GOOGLE_CLIENT_SECRET=yyy \
  CIRIS_MANAGER_CONFIG=~/.config/ciris-manager/config.yml \
  python deployment/run-ciris-manager-api.py

# GUI
cd CIRISGUI/apps/agui && npm run dev

# Single agent
docker-compose -f docker-compose-api-discord-mock.yml up -d
```

### Common Issues & Solutions

1. **401 Unauthorized**: OAuth not configured - set GOOGLE_CLIENT_ID/SECRET
2. **Agent exits immediately**: Must set `CIRIS_ADAPTER=api`
3. **nginx 502 errors**: Check if services are running on expected ports
4. **Docker network issues**: Use `ciris-network` (not `cirisagent_default`)

### Architecture Overview
```
[Browser] → [nginx:80] → ├─ [GUI:3000] → [Manager:8888] → [Docker]
                         ├─ [Manager:8888]              ↘
                         └─ [Agents:808X] ← ← ← ← ← ← ← ← [Agents]
```

### Key Files
- Manager config: `~/.config/ciris-manager/config.yml`
- nginx config: `/home/ciris/nginx/nginx.conf`
- Agent logs: `docker logs ciris-<agent-id>`
- Manager logs: `/tmp/ciris-manager.log`

### Testing
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/ciris_manager/test_routing.py

# Check coverage
python -m pytest --cov=ciris_manager
```

### Production Notes
- Manager runs as systemd service: `sudo systemctl restart ciris-manager-api`
- Manager updates require SSH access
- Agent updates are automatic (Docker pulls every 60s)

## Important Reminders

1. **Always check logs first** - Don't restart without understanding errors
2. **Use Pydantic models** - No Dict[str, Any] allowed
3. **Docker is source of truth** - For discovery and routing
4. **Test before committing** - Ensure >80% coverage on new code

For detailed documentation, see `docs/README.md`.