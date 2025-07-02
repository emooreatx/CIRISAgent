# CIRISGUI - Updated for v1 API

This GUI has been updated to work directly with the CIRIS v1 API, showing the fruits of our labor!

## What's New

### ✅ Direct v1 API Integration
- Uses the actual CIRIS API v1 endpoints (all 35 of them!)
- No more wrapper layer - direct connection to the improved API
- Full authentication with role-based access control
- WebSocket support for real-time updates

### 🚀 Quick Start

1. **Start the services** (from CIRISGUI directory):
   ```bash
   ./scripts/start-direct.sh
   ```

2. **Access the GUI**:
   - Web UI: http://localhost:3000
   - API: http://localhost:8080

3. **Login with default credentials**:
   - Username: `admin`
   - Password: `ciris_admin_password`

### 📱 Features Available

#### Home Dashboard
- Real-time agent status
- Cognitive state display
- Agent identity and capabilities
- Quick access to all sections

#### Communications (/comms)
- Chat with the agent
- Real-time message updates via WebSocket
- Conversation history
- Channel-based communication

#### System Status (/system)
- Service health monitoring
- Resource usage tracking
- Runtime control (pause/resume)
- Processor and adapter management

#### Audit Trail (/audit)
- Complete system activity log
- Filter by service, action, time
- Export audit data

#### Memory (/memory)
- Search the knowledge graph
- View memory nodes
- Memory statistics

#### Configuration (/config) - Admin only
- View and update system configuration
- Backup and restore settings

#### Wise Authority (/wa) - Authority only
- View deferred decisions
- Resolve pending approvals

### 🛠️ Technical Details

The GUI now uses:
- `api-client-v1.ts` - Complete v1 API client with all endpoints
- Direct authentication to v1 auth endpoints
- Proper token management and role-based access
- WebSocket connection to `/v1/ws` for real-time updates

### 🐛 Troubleshooting

1. **Container won't start**: Make sure no other services are using ports 3000 or 8080
2. **Login fails**: Check that the API container is healthy with `docker ps`
3. **WebSocket disconnects**: The API might be restarting - wait a moment and refresh

### 🎉 Improvements Demonstrated

This GUI showcases all the improvements we've made:
- **Type Safety**: Zero `Dict[str, Any]` - all data uses typed schemas
- **35 v1 Endpoints**: All operational and tested
- **19 Services**: All healthy and monitored
- **Mock LLM**: Works offline for testing
- **Runtime Control**: Pause/resume processors and adapters
- **Audit Trail**: Complete system transparency
- **Role-Based Access**: Different features for different roles

Enjoy exploring the improved CIRIS system through this updated GUI!