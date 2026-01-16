#!/bin/bash

# Quick setup script for knowledge base integration
# Usage: ./scripts/setup-kb.sh <local-kb-id> <national-kb-id>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <local-kb-id> <national-kb-id>"
    echo ""
    echo "Example:"
    echo "  $0 ABC123XYZ DEF456UVW"
    exit 1
fi

LOCAL_KB_ID=$1
NATIONAL_KB_ID=$2

echo "Setting up knowledge bases..."
echo "Local KB ID: $LOCAL_KB_ID"
echo "National KB ID: $NATIONAL_KB_ID"

# Export for current session
export LOCAL_KB_ID=$LOCAL_KB_ID
export NATIONAL_KB_ID=$NATIONAL_KB_ID

# Deploy agent with KB IDs
echo ""
echo "Deploying agent..."
cd infrastructure/agent-stack
npm install
cdk deploy --require-approval never

echo ""
echo "✅ Knowledge bases configured and agent deployed!"
echo ""
echo "To use in future sessions, export these variables:"
echo "  export LOCAL_KB_ID=$LOCAL_KB_ID"
echo "  export NATIONAL_KB_ID=$NATIONAL_KB_ID"
