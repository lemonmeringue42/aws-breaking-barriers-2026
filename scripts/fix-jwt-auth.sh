#!/bin/bash
set -e

echo "🔧 Fixing JWT authentication mismatch..."
echo ""
echo "This will redeploy the agent with the current Cognito configuration."
echo ""

# Check if Amplify backend is deployed
if [ ! -f "amplify_outputs.json" ]; then
    echo "❌ amplify_outputs.json not found. Please deploy Amplify backend first:"
    echo "   npm run deploy:amplify"
    exit 1
fi

# Get current Cognito config
USER_POOL_ID=$(cat amplify_outputs.json | jq -r '.auth.user_pool_id')
REGION=$(cat amplify_outputs.json | jq -r '.auth.aws_region')

echo "Current Cognito Configuration:"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Region: $REGION"
echo ""

# Redeploy agent
echo "Redeploying agent..."
cd infrastructure/agent-stack
npm install
cdk deploy --require-approval never

cd ../..

# Sync gateway
echo ""
echo "Syncing gateway..."
./scripts/sync-gateway.sh

echo ""
echo "✅ Agent redeployed with correct JWT configuration!"
echo ""
echo "Please restart your dev server: npm run dev"
