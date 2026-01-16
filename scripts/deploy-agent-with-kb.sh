#!/bin/bash
set -e

# Knowledge Base IDs - Update these with your actual KB IDs
export LOCAL_KB_ID="${LOCAL_KB_ID:-}"
export NATIONAL_KB_ID="${NATIONAL_KB_ID:-}"

echo "Deploying agent with knowledge bases..."
echo "Local KB ID: ${LOCAL_KB_ID:-Not set}"
echo "National KB ID: ${NATIONAL_KB_ID:-Not set}"

cd infrastructure/agent-stack
npm install
cdk deploy --require-approval never

echo "✅ Agent deployed with knowledge base integration"
