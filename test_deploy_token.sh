#!/bin/bash
# Test if the DEPLOY_TOKEN in GitHub secrets matches production

echo "Testing deployment token configuration..."
echo

# Production token (from /etc/ciris-manager/environment)
PROD_TOKEN="2e5ed5864e7ba97226a29f88ea570d8f9e868ea2a8c1a542a30f550511afd675"

# Test with production token
echo "1. Testing with production token:"
curl -s -w "\nHTTP_STATUS:%{http_code}" https://agents.ciris.ai/manager/v1/status \
  -H "Authorization: Bearer $PROD_TOKEN" | tail -1

echo
echo "2. Testing deployment notification endpoint (dry run):"
response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST https://agents.ciris.ai/manager/v1/updates/notify \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_image": "ghcr.io/cirisai/ciris-agent:test",
    "gui_image": "ghcr.io/cirisai/ciris-gui:test",
    "strategy": "canary",
    "dry_run": true,
    "source": "manual_test"
  }')

http_status=$(echo "$response" | grep "HTTP_STATUS:" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_STATUS:/d')

echo "HTTP Status: $http_status"
echo "Response: $body"

if [[ "$http_status" =~ ^2[0-9][0-9]$ ]]; then
  echo
  echo "✅ Production token is working correctly"
else
  echo
  echo "❌ Production token failed"
fi