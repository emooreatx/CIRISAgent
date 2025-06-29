# SDK Test Summary

## Test Results
As of June 29, 2025, testing the CIRIS SDK v1 against the API v1.0 revealed:

### Working Endpoints (4/35)
1. **POST /v1/auth/login** - ✅ Authentication works
2. **GET /v1/auth/me** - ✅ Get current user info
3. **POST /v1/auth/refresh** - ✅ Token refresh (manual update needed)
4. **GET /v1/system/health** - ✅ Health check (no auth required)

### Issues Found

#### API Issues
1. **Service Registry Not Available**: The API routes have `service_registry = None`, causing all service lookups to fail
2. **Only 1/19 Services Registered**: Only AuthenticationService is visible
3. **204 No Content Handling**: Logout returns 204 which SDK can't parse

#### SDK Issues
1. **Token Management**: `client.api_key` not updated after login (use `client._transport.api_key`)
2. **Exception Naming**: Import `CIRISAPIError` not `CIRISAuthError`
3. **Missing 204 Support**: SDK expects all responses to be JSON

#### Test Fixes Applied
1. Check `client._transport.api_key` instead of `client.api_key`
2. Use `CIRISAPIError` with status code check for auth failures
3. Call `client.auth.get_current_user()` not `client.auth.me()`
4. Use context managers for proper client lifecycle

### Next Steps
1. Fix service registry injection in API adapter
2. Add 204 No Content support to SDK transport
3. Update client to expose transport's api_key as property
4. Complete testing once services are available