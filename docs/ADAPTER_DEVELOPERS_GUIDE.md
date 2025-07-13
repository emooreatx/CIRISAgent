# CIRIS Engine Adapter Developer's Guide

## Overview

The CIRIS Engine uses a sophisticated adapter architecture to interface with different platforms (Discord, CLI, API, etc.) while maintaining platform-agnostic core functionality. This guide provides comprehensive documentation for developing new adapters and maintaining existing ones.

## Architecture Principles

### 1. Platform Logic Isolation
- **Core Rule**: All platform-specific logic must reside within `ciris_engine/adapters/`
- **Core modules** (processor, sinks, action_handlers, guardrails, etc.) must remain platform-agnostic
- **Communication** between core and platforms happens through well-defined service protocols

### 2. Service-Oriented Design
- Adapters implement standardized service interfaces (`CommunicationService`, `WiseAuthorityService`, `ToolService`, `RuntimeControlService`)
- Core components interact with adapters through the `ServiceRegistry` and protocol interfaces
- Multiple adapters can provide the same service type with different priorities

### 3. Event-Driven Architecture
- Adapters observe platform events and translate them to CIRIS schemas
- Core components process standardized events regardless of origin platform
- Platform-specific responses are handled by the appropriate adapter

## Adapter Directory Structure

```
ciris_engine/adapters/
├── {platform_name}/
│   ├── __init__.py
│   ├── adapter.py          # Platform orchestrator
│   ├── {platform}_adapter.py  # Core adapter implementation
│   ├── {platform}_observer.py # Event observation and processing
│   ├── config.py          # Platform-specific configuration
│   └── ... (platform-specific modules)
├── base.py                # Base adapter functionality
└── base_observer.py       # Base observer functionality
```

### Example: Discord Adapter Structure
```
ciris_engine/adapters/discord/
├── __init__.py
├── adapter.py                        # DiscordPlatform orchestrator
├── discord_adapter.py                # Main Discord adapter
├── discord_observer.py               # Message observation
├── discord_channel_manager.py        # Channel management
├── discord_message_handler.py        # Message handling
├── discord_guidance_handler.py       # Human guidance requests
├── discord_tool_handler.py           # Tool execution
├── discord_tools.py                  # Discord-specific tools
└── config.py                         # Discord configuration
```

## Core Components

### 1. Platform Orchestrator (`adapter.py`)

The main entry point that coordinates all platform components:

```python
class DiscordPlatform:
    """Main Discord platform orchestrator."""
    
    def __init__(self, runtime, **kwargs):
        self.runtime = runtime
        self.config = DiscordAdapterConfig()
        self.config.load_env_vars()
        
        # Initialize components
        self.discord_adapter = DiscordAdapter(self.token, **kwargs)
        self.discord_observer = DiscordObserver(**services)
        self.client = discord.Client(intents=self.config.get_intents())
        
    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        """Return services this platform provides."""
        return [
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "fetch_messages"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.WISE_AUTHORITY,
                provider=self.discord_adapter,
                priority=Priority.HIGH,
                handlers=["DeferHandler", "SpeakHandler"],
                capabilities=["fetch_guidance", "send_deferral"]
            ),
            AdapterServiceRegistration(
                service_type=ServiceType.TOOL,
                provider=self.discord_tool_service,
                priority=Priority.NORMAL,
                handlers=["ToolHandler"],
                capabilities=["execute_tool", "list_tools", "get_tool_info"]
            ),
            # RuntimeControlService would be added here if platform supports it
        ]
```

**Key Responsibilities:**
- Initialize all platform components
- Register services with the runtime
- Handle platform lifecycle (start/stop)
- Coordinate between adapter components

### 2. Core Adapter (`{platform}_adapter.py`)

Implements the service interfaces and handles platform communication:

```python
class DiscordAdapter(CommunicationService):
    """Discord communication adapter implementing service protocols."""
    
    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send message to Discord channel."""
        try:
            return await self._message_handler.send_message_to_channel(
                channel_id, content
            )
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False
    
    async def fetch_messages(self, channel_id: str, limit: int) -> List[FetchedMessage]:
        """Fetch messages from Discord channel."""
        # Implementation...
    
    async def get_capabilities(self) -> List[str]:
        """Return adapter capabilities."""
        return ["send_message", "fetch_messages", "guild_support"]
```

**Key Responsibilities:**
- Implement service protocol interfaces
- Handle platform-specific API calls
- Convert between platform and CIRIS data formats
- Provide capability reporting

### 3. Observer (`{platform}_observer.py`)

Monitors platform events and converts them to CIRIS events:

```python
class DiscordObserver:
    """Observes Discord events and processes them for CIRIS."""
    
    async def handle_incoming_message(self, discord_message: DiscordMessage):
        """Process incoming Discord message."""
        
        # Filter and validate
        if not self._should_process_message(discord_message):
            return
            
        # Apply secrets filtering
        filtered_message = await self._process_message_secrets(discord_message)
        
        # Apply message filtering  
        filter_result = await self._apply_message_filtering(filtered_message)
        
        if filter_result.should_process:
            # Send to core processing
            await self._handle_observation(filtered_message, filter_result)
```

**Key Responsibilities:**
- Monitor platform events (messages, reactions, etc.)
- Apply platform-specific filtering
- Convert platform events to CIRIS schemas
- Forward processed events to core components

### 4. Configuration (`config.py`)

Manages platform-specific settings:

```python
class DiscordAdapterConfig:
    """Configuration for Discord adapter."""
    
    # Authentication
    bot_token: Optional[str] = None
    
    # Channel configuration
    monitored_channel_ids: List[str] = []
    home_channel_id: Optional[str] = None
    deferral_channel_id: Optional[str] = None
    
    # Bot behavior
    respond_to_mentions: bool = True
    respond_to_dms: bool = True
    
    def load_env_vars(self):
        """Load configuration from environment variables."""
        self.bot_token = get_env_var('DISCORD_BOT_TOKEN')
        # ... load other vars
        
    def get_intents(self) -> discord.Intents:
        """Get Discord intents configuration."""
        intents = discord.Intents.default()
        intents.message_content = self.enable_message_content
        return intents
```

## Service Protocol Implementation

### Communication Service

All communication adapters must implement:

```python
async def send_message(self, channel_id: str, content: str) -> bool
async def fetch_messages(self, channel_id: str, limit: int) -> List[FetchedMessage]
async def is_healthy() -> bool
async def get_capabilities() -> List[str]
```

### Wise Authority Service

For human guidance and escalation:

```python
async def send_deferral(self, deferral: DeferralRequest) -> str
async def fetch_guidance(self, context: GuidanceContext) -> Optional[str]
```

### Tool Service

For platform-specific tool execution:

```python
async def execute_tool(self, tool_name: str, parameters: dict) -> ToolExecutionResult
async def list_tools() -> List[str]
async def get_tool_info(self, tool_name: str) -> Optional[ToolInfo]
async def get_all_tool_info() -> List[ToolInfo]
async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[ToolExecutionResult]
async def validate_parameters(self, tool_name: str, parameters: dict) -> bool
```

### Runtime Control Service

For controlling CIRIS runtime behavior (currently only implemented by API adapter):

```python
async def pause_processing() -> bool
async def resume_processing() -> bool
async def request_state_transition(self, target_state: str) -> bool
async def get_runtime_status() -> RuntimeStatus
async def single_step_processing() -> bool
async def get_processing_queue_status() -> Dict[str, Any]
```

**Note:** RuntimeControlService is typically only provided by administrative interfaces like the API adapter. Most adapters do not need to implement this service as it provides sensitive runtime control capabilities.

## Current Service Implementations

### Services by Adapter

**CLI Adapter:**
- ✅ CommunicationService (Priority: HIGH)
- ✅ ToolService (Priority: HIGH)
- ❌ WiseAuthorityService
- ❌ RuntimeControlService

**API Adapter:**
- ✅ CommunicationService (Priority: NORMAL)
- ✅ ToolService (Priority: NORMAL)
- ❌ WiseAuthorityService
- ✅ RuntimeControlService (Priority: HIGH) - **UNIQUE**

**Discord Adapter:**
- ✅ CommunicationService (Priority: HIGH)
- ✅ ToolService (Priority: NORMAL)
- ✅ WiseAuthorityService (Priority: HIGH) - **UNIQUE**
- ❌ RuntimeControlService

### Service Capabilities Summary

| Service Type | CLI | API | Discord | Description |
|-------------|-----|-----|---------|-------------|
| Communication | ✅ | ✅ | ✅ | Send/receive messages |
| Tool | ✅ | ✅ | ✅ | Execute platform tools |
| Wise Authority | ❌ | ❌ | ✅ | Human guidance/deferrals |
| Runtime Control | ❌ | ✅ | ❌ | Control agent runtime |

## Data Schemas

### Standard Message Format

All platforms convert their messages to `IncomingMessage`:

```python
@dataclass
class IncomingMessage:
    message_id: str
    author_id: str  
    author_name: str
    content: str
    destination_id: str
    timestamp: str
    is_bot: bool = False
    reference_message_id: Optional[str] = None
```

### Platform-Specific Extensions

Platforms can extend base schemas for their specific needs:

```python
@dataclass  
class DiscordMessage(IncomingMessage):
    """Discord-specific message with additional fields."""
    guild_id: Optional[str] = None
    thread_id: Optional[str] = None
    mention_everyone: bool = False
    
    @property
    def channel_id(self) -> str:
        """Backward compatibility alias."""
        return self.destination_id
```

## Development Guidelines

### 1. Adding a New Adapter

**Step 1: Create Directory Structure**
```bash
mkdir -p ciris_engine/adapters/myplatform
touch ciris_engine/adapters/myplatform/__init__.py
touch ciris_engine/adapters/myplatform/adapter.py
touch ciris_engine/adapters/myplatform/myplatform_adapter.py
touch ciris_engine/adapters/myplatform/config.py
```

**Step 2: Implement Base Classes**
```python
# myplatform_adapter.py
from ciris_engine.protocols.services import CommunicationService
from ciris_engine.adapters.base import BaseAdapter

class MyPlatformAdapter(BaseAdapter, CommunicationService):
    def __init__(self, **kwargs):
        super().__init__()
        # Platform-specific initialization
        
    async def send_message(self, channel_id: str, content: str) -> bool:
        # Implement platform message sending
        pass
        
    async def fetch_messages(self, channel_id: str, limit: int) -> List[FetchedMessage]:
        # Implement platform message fetching  
        pass
```

**Step 3: Create Platform Orchestrator**
```python
# adapter.py
class MyPlatformPlatform:
    def __init__(self, runtime, **kwargs):
        self.runtime = runtime
        self.config = MyPlatformConfig()
        self.adapter = MyPlatformAdapter(**kwargs)
        
    def get_services_to_register(self) -> List[AdapterServiceRegistration]:
        return [
            AdapterServiceRegistration(
                service_type=ServiceType.COMMUNICATION,
                provider=self.adapter,
                priority=Priority.MEDIUM,
                handlers=["SpeakHandler", "ObserveHandler"],
                capabilities=["send_message", "fetch_messages"]
            ),
            # Add other services if your adapter provides them:
            # - WiseAuthorityService
            # - ToolService  
            # - RuntimeControlService
        ]
```

**Step 4: Register with Runtime**
```python
# In main.py or runtime initialization
if platform_enabled("myplatform"):
    platform = MyPlatformPlatform(runtime, **platform_config)
    runtime.register_platform(platform)
```

### 2. Best Practices

**Configuration Management:**
- Use environment variables for sensitive data
- Provide sensible defaults
- Support both environment and programmatic configuration
- Validate configuration on startup

**Error Handling:**
- Gracefully handle platform API failures
- Return appropriate error responses (False, None, empty lists)
- Log errors with sufficient context
- Implement retry logic for transient failures

**Testing:**
- Mock platform APIs in tests
- Test both success and failure scenarios
- Use fixtures for reusable test components
- Test service protocol compliance

**Performance:**
- Implement connection pooling where applicable
- Use async/await properly
- Add rate limiting for API calls
- Monitor resource usage

**Security:**
- Never log sensitive tokens or credentials
- Validate all incoming data
- Sanitize outgoing messages
- Use encryption for stored secrets

### 3. Debugging and Monitoring

**Logging:**
```python
import logging
logger = logging.getLogger(__name__)

async def send_message(self, channel_id: str, content: str) -> bool:
    logger.debug(f"Sending message to {channel_id}: {content[:50]}...")
    try:
        result = await self._platform_api.send(channel_id, content)
        logger.info(f"Message sent successfully to {channel_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {channel_id}: {e}", exc_info=True)
        return False
```

**Health Checks:**
```python
async def is_healthy(self) -> bool:
    """Check if adapter is healthy and can communicate with platform."""
    try:
        # Test platform connectivity
        await self._platform_api.ping()
        return True
    except Exception as e:
        logger.warning(f"Health check failed: {e}")
        return False
```

**Telemetry Integration:**
```python
from ciris_engine.persistence import add_correlation

async def send_message(self, channel_id: str, content: str) -> bool:
    correlation = ServiceCorrelation(
        service_type="myplatform",
        action_type="send_message", 
        request_data={"channel_id": channel_id, "content_length": len(content)},
        timestamp=datetime.now(timezone.utc)
    )
    
    try:
        result = await self._send_implementation(channel_id, content)
        correlation.response_data = {"success": result}
        return result
    except Exception as e:
        correlation.response_data = {"success": False, "error": str(e)}
        raise
    finally:
        await add_correlation(correlation)
```

## Current Architecture Status

### ✅ Properly Isolated Components
- `ciris_engine/sinks/` - Uses abstract service protocols
- `ciris_engine/guardrails/` - Platform-agnostic
- `ciris_engine/protocols/services.py` - Properly abstracts platform differences
- Most `ciris_engine/action_handlers/` modules
- Core `ciris_engine/dma/` modules

### ⚠️ Known Isolation Violations

The following areas still contain platform-specific logic that should be refactored:

1. **Context Builder** (`ciris_engine/context/builder.py`): Contains hardcoded platform channel resolution
2. **Action Handler Base** (`ciris_engine/action_handlers/base_handler.py`): Platform-specific channel ID conversion
3. **Utils Constants** (`ciris_engine/utils/constants.py`): Platform-specific constants in core utils
4. **Core Schemas** (`ciris_engine/schemas/config_schemas_v1.py`): Direct adapter config coupling

### 🎯 Refactoring Roadmap

To achieve complete platform logic isolation:

1. **Abstract Channel Resolution**: Move platform-specific channel ID logic to adapters
2. **Decouple Schema Dependencies**: Remove direct adapter config imports from core schemas  
3. **Centralize Platform Detection**: Create adapter-provided platform context abstractions
4. **Extract Platform Constants**: Move all platform-specific constants to adapter configs

## Testing Adapters

### Unit Testing

```python
# test_myplatform_adapter.py
import pytest
from unittest.mock import AsyncMock, Mock
from myplatform_adapter import MyPlatformAdapter

@pytest.fixture
def mock_platform_api():
    return AsyncMock()

@pytest.fixture  
def adapter(mock_platform_api):
    adapter = MyPlatformAdapter()
    adapter._platform_api = mock_platform_api
    return adapter

@pytest.mark.asyncio
async def test_send_message_success(adapter, mock_platform_api):
    mock_platform_api.send.return_value = True
    
    result = await adapter.send_message("channel123", "test message")
    
    assert result is True
    mock_platform_api.send.assert_called_once_with("channel123", "test message")

@pytest.mark.asyncio  
async def test_send_message_failure(adapter, mock_platform_api):
    mock_platform_api.send.side_effect = Exception("API Error")
    
    result = await adapter.send_message("channel123", "test message") 
    
    assert result is False
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_full_message_flow(adapter):
    """Test complete message flow from platform to core processing."""
    
    # Simulate platform message
    platform_message = create_test_platform_message()
    
    # Process through observer
    await adapter.observer.handle_incoming_message(platform_message)
    
    # Verify core processing was triggered
    adapter.multi_service_sink.observe_message.assert_called_once()
    
    # Verify message conversion
    call_args = adapter.multi_service_sink.observe_message.call_args
    processed_message = call_args[0][1]
    assert isinstance(processed_message, IncomingMessage)
    assert processed_message.content == platform_message.content
```

## Performance Considerations

### Connection Management
- Implement connection pooling for HTTP-based platforms
- Use persistent connections where possible
- Handle connection timeouts gracefully
- Monitor connection health

### Rate Limiting
```python
import asyncio
from collections import defaultdict
from time import time

class RateLimiter:
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
    
    async def acquire(self, key: str = "default") -> bool:
        now = time()
        window_start = now - self.time_window
        
        # Remove old requests
        self.requests[key] = [req_time for req_time in self.requests[key] 
                             if req_time > window_start]
        
        # Check if we can make request
        if len(self.requests[key]) >= self.max_requests:
            return False
            
        self.requests[key].append(now)
        return True

# Usage in adapter
rate_limiter = RateLimiter(max_requests=30, time_window=60)  # 30 requests per minute

async def send_message(self, channel_id: str, content: str) -> bool:
    if not await rate_limiter.acquire(f"send_message_{channel_id}"):
        logger.warning(f"Rate limit exceeded for channel {channel_id}")
        return False
    
    return await self._send_implementation(channel_id, content)
```

### Async Best Practices
- Use `asyncio.gather()` for concurrent operations
- Implement proper timeout handling
- Use connection pooling for HTTP clients
- Avoid blocking operations in async functions

## Security Guidelines

### Token Management
```python
import os
from ciris_engine.secrets import SecretsService

class SecureConfig:
    def __init__(self, secrets_service: SecretsService):
        self.secrets = secrets_service
        
    def get_api_token(self) -> str:
        """Get API token from secure storage."""
        token = self.secrets.get_secret("myplatform_api_token")
        if not token:
            raise ValueError("MyPlatform API token not configured")
        return token
```

### Input Validation
```python
def validate_channel_id(channel_id: str) -> bool:
    """Validate platform channel ID format."""
    if not channel_id or not isinstance(channel_id, str):
        return False
    if len(channel_id) > 100:  # Reasonable limit
        return False
    if not channel_id.replace('-', '').replace('_', '').isalnum():
        return False
    return True

async def send_message(self, channel_id: str, content: str) -> bool:
    if not validate_channel_id(channel_id):
        logger.warning(f"Invalid channel ID: {channel_id}")
        return False
        
    if len(content) > self.max_message_length:
        logger.warning(f"Message too long: {len(content)} chars")
        return False
        
    return await self._send_implementation(channel_id, content)
```

### Data Sanitization
```python
import html
import re

def sanitize_message_content(content: str) -> str:
    """Sanitize message content for safe processing."""
    # Remove control characters
    content = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', content)
    
    # HTML escape
    content = html.escape(content)
    
    # Truncate if too long
    if len(content) > 2000:
        content = content[:1997] + "..."
        
    return content
```

## Migration and Compatibility

### Versioning Adapters
```python
class MyPlatformAdapter:
    """MyPlatform adapter v2.1.0"""
    
    ADAPTER_VERSION = "2.1.0"
    MIN_PLATFORM_API_VERSION = "1.5.0"
    
    def __init__(self):
        self._check_compatibility()
        
    def _check_compatibility(self):
        """Check platform API compatibility."""
        api_version = self._get_platform_api_version()
        if not self._is_compatible(api_version):
            raise RuntimeError(f"Platform API {api_version} not compatible")
```

### Backward Compatibility
```python
async def send_message(self, channel_id: str, content: str, **kwargs) -> bool:
    """Send message with backward compatibility."""
    
    # Handle legacy channel ID format
    if channel_id.startswith("legacy:"):
        channel_id = self._convert_legacy_channel_id(channel_id)
        
    # Support deprecated parameters
    if "legacy_param" in kwargs:
        logger.warning("legacy_param is deprecated, use new_param instead")
        kwargs["new_param"] = kwargs.pop("legacy_param")
        
    return await self._send_implementation(channel_id, content, **kwargs)
```

## Troubleshooting Common Issues

### Connection Issues
```python
async def _handle_connection_error(self, error: Exception) -> bool:
    """Handle platform connection errors with retry logic."""
    if isinstance(error, (TimeoutError, ConnectionError)):
        logger.warning(f"Connection error, retrying: {error}")
        await asyncio.sleep(1)
        return True  # Retry
    elif isinstance(error, AuthenticationError):
        logger.error("Authentication failed - check credentials")
        return False  # Don't retry
    else:
        logger.error(f"Unexpected error: {error}")
        return False
```

### Message Formatting Issues
```python
def _format_message_for_platform(self, content: str) -> str:
    """Format CIRIS message for platform-specific requirements."""
    
    # Platform-specific formatting
    if self.platform_requires_markdown:
        content = self._convert_to_markdown(content)
    
    # Handle length limits
    if len(content) > self.max_message_length:
        content = self._split_long_message(content)
        
    return content
```

### Rate Limit Handling
```python
async def _handle_rate_limit(self, retry_after: int):
    """Handle platform rate limiting."""
    logger.warning(f"Rate limited, waiting {retry_after} seconds")
    await asyncio.sleep(retry_after)
    
    # Update rate limiter state
    self.rate_limiter.backoff(retry_after)
```

This guide provides a comprehensive foundation for developing and maintaining CIRIS Engine adapters. Follow these patterns and principles to ensure your adapter integrates seamlessly with the core architecture while maintaining proper isolation of platform-specific concerns.