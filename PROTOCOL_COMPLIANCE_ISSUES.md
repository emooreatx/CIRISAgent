# Protocol Compliance Issues Report

## Summary
Found several protocol compliance issues where classes claim to implement protocols but have mismatched method signatures. These need to be reviewed to determine if the protocol or implementation should be updated.

## Critical Issues Found

### 1. AuthenticationService - `create_channel_token` method
**File**: `ciris_engine/logic/services/infrastructure/authentication.py`
**Issue**: Method is `async` in implementation but synchronous in protocol
- **Protocol signature**: `def create_channel_token(self, wa_id: str, channel_id: str, ttl: int = 3600) -> str:`
- **Implementation signature**: `async def create_channel_token(self, wa_id: str, channel_id: str, ttl: int = 3600) -> str:`
- **Action needed**: Either make protocol method async or implementation sync

### 2. GraphAuditService - `log_action` method
**File**: `ciris_engine/logic/services/graph/audit_service.py`
**Issue**: Method signature completely different from protocol
- **Protocol signature**: 
  ```python
  async def log_action(
      self,
      action: HandlerActionType,
      actor_id: str,
      thought_id: Optional[str] = None,
      task_id: Optional[str] = None,
      context: Optional[dict] = None,
      metadata: Optional[dict] = None
  ) -> None:
  ```
- **Implementation signature**:
  ```python
  async def log_action(
      self,
      action_type: HandlerActionType,
      context: AuditActionContext,
      outcome: Optional[str] = None
  ) -> None:
  ```
- **Action needed**: Update either protocol or implementation to match

### 3. ConfigurationFeedbackLoop - ServiceProtocol compliance
**File**: `ciris_engine/logic/infrastructure/sub_services/configuration_feedback_loop.py`
**Issue**: Class extends `Service` but tests expect it to implement `ServiceProtocol`
- **Current**: `class ConfigurationFeedbackLoop(Service):`
- **Expected**: Should implement `ServiceProtocol` methods (`start()`, `stop()`, etc.)
- **Action needed**: Verify if this should implement ServiceProtocol or if tests are incorrect

### 4. OpenAICompatibleClient - `call_llm_structured` method
**File**: `ciris_engine/logic/services/runtime/llm_service.py`
**Issue**: Parameter type mismatch
- **Protocol expects**: `messages: List[MessageDict]`
- **Implementation has**: `messages: List[dict]`
- **Action needed**: Update implementation to use proper type

### 5. CIRISNodeClient - Multiple `log_action` calls
**File**: `ciris_engine/logic/adapters/cirisnode_client.py`
**Issue**: All calls to `audit_service.log_action()` use wrong signature
- **Current calls**: Pass `outcome` as keyword arg and `AuditActionContext` as second parameter
- **Expected by protocol**: Different parameter order and types
- **Action needed**: Update all calls to match protocol signature

## Less Critical Issues

### 6. Missing return type annotations
Multiple service methods are missing return type annotations, making protocol compliance harder to verify:
- `ciris_engine/schemas/services/nodes.py` - multiple methods
- `ciris_engine/logic/utils/profile_loader.py` - multiple methods
- Various service implementations

### 7. Type mismatches in schema classes
Several schema classes have field type mismatches:
- `datetime | None` passed where `datetime` expected
- `str` passed where enum types expected
- Dict types not matching expected schemas

## Recommendations

1. **For critical issues 1-5**: These need immediate attention as they break protocol contracts
2. **For type annotations**: Add missing annotations to improve type safety
3. **For schema mismatches**: Update schemas to allow None values where appropriate

## Next Steps

1. Review each issue to determine if protocol or implementation should change
2. Update code to ensure protocol compliance
3. Add tests to verify protocol compliance
4. Consider using Protocol runtime checks for critical services