#!/bin/bash
# Quick test of agent with a JWT token
# Usage: ./test-agent-curl.sh <jwt-token>

if [ -z "$1" ]; then
    echo "Usage: $0 <jwt-token>"
    echo ""
    echo "To get your JWT token:"
    echo "1. Open browser DevTools (F12)"
    echo "2. Go to Console tab"
    echo "3. Run: (await fetchAuthSession()).tokens.idToken.toString()"
    echo "4. Copy the token and run: $0 <token>"
    exit 1
fi

TOKEN="$1"
RUNTIME_ARN="arn:aws:bedrock-agentcore:us-west-2:732033934792:runtime/agent_agentstack_citizensadv2-K34b90BM5n"
REGION="us-west-2"
QUERY="${2:-I need help with Universal Credit}"

# URL encode the ARN
ENCODED_ARN=$(echo "$RUNTIME_ARN" | sed 's/:/%3A/g' | sed 's/\//%2F/g')
URL="https://bedrock-agentcore.${REGION}.amazonaws.com/runtimes/${ENCODED_ARN}/invocations?qualifier=DEFAULT"

echo "Testing agent..."
echo "Query: $QUERY"
echo ""

curl -X POST "$URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$QUERY\", \"user_id\": \"test-user\", \"session_id\": \"test-session\"}" \
  2>&1

echo ""
