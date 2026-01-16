#!/bin/bash
# Fix agent JWT authorizer to accept current Cognito client ID

RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:732033934792:runtime/agent_agentstack_citizensadv2-pbN1dLH2Vu"
USER_POOL_ID="us-west-2_OSUEpnHmo"
CLIENT_ID="1vctuearov1eotv5soq7r3uvp0"
REGION="us-west-2"

echo "Updating agent JWT authorizer configuration..."
echo "Runtime: $RUNTIME_ARN"
echo "User Pool: $USER_POOL_ID"
echo "Client ID: $CLIENT_ID"
echo ""

# Update the runtime authorizer
aws bedrock-agentcore update-runtime \
  --runtime-arn "$RUNTIME_ARN" \
  --region "$REGION" \
  --authorizer-configuration "{
    \"customJWTAuthorizer\": {
      \"discoveryUrl\": \"https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}/.well-known/openid-configuration\",
      \"allowedClients\": [\"${CLIENT_ID}\"]
    }
  }"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Agent authorizer updated successfully!"
    echo "Test with: ./scripts/test-agent-curl.sh <your-token>"
else
    echo ""
    echo "❌ Failed to update authorizer"
fi
