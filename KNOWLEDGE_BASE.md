# Knowledge Base Integration

The Citizens Advice Agent integrates with two Bedrock Knowledge Bases:

## Knowledge Bases

### 1. National Knowledge Base (`NATIONAL_KB_ID`)
Contains UK-wide Citizens Advice information:
- Benefits and financial support guidance
- Employment rights and workplace issues
- Consumer rights and protections
- Housing law and tenancy rights
- Debt management advice
- Immigration guidance

### 2. Local Knowledge Base (`LOCAL_KB_ID`)
Contains region-specific information:
- Local Citizens Advice bureau contact details
- Regional services and support programs
- Local authority specific guidance
- Area-specific resources and referrals

## Setup

### 1. Set Knowledge Base IDs

Export your knowledge base IDs as environment variables:

```bash
export LOCAL_KB_ID="your-local-kb-id"
export NATIONAL_KB_ID="your-national-kb-id"
```

### 2. Deploy Agent

```bash
./scripts/deploy-agent-with-kb.sh
```

Or manually:

```bash
cd infrastructure/agent-stack
LOCAL_KB_ID=your-local-kb-id NATIONAL_KB_ID=your-national-kb-id cdk deploy
```

## How It Works

The agent automatically queries the knowledge bases when:

1. **National KB** - For general UK-wide advice questions
   - Example: "How do I apply for Universal Credit?"
   - The agent calls `query_national_kb(query)` to retrieve relevant information

2. **Local KB** - For region-specific queries
   - Example: "Where is my nearest Citizens Advice bureau?"
   - The agent calls `query_local_kb(query, region)` with the user's region

## Tools Available to Agent

### `query_national_kb(query: str) -> str`
Queries the national knowledge base for UK-wide advice.

**Parameters:**
- `query`: The question or topic to search for

**Returns:**
- Formatted results with relevance scores and sources

### `query_local_kb(query: str, region: Optional[str]) -> str`
Queries the local knowledge base for region-specific information.

**Parameters:**
- `query`: The question or topic to search for
- `region`: Optional region filter (e.g., "London", "Scotland")

**Returns:**
- Formatted local information with sources

## Testing

After deployment, test the knowledge base integration:

```bash
# Test national KB
curl -X POST https://your-agent-url/invoke \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "How do I apply for Universal Credit?"}'

# Test local KB
curl -X POST https://your-agent-url/invoke \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Find my local Citizens Advice bureau", "region": "London"}'
```

## Permissions

The agent role has been granted:
- `bedrock:Retrieve` permission for all knowledge bases in the account
- Access to query both local and national knowledge bases

## Troubleshooting

If knowledge bases aren't working:

1. **Check IDs are set:**
   ```bash
   echo $LOCAL_KB_ID
   echo $NATIONAL_KB_ID
   ```

2. **Verify permissions:**
   - Agent role has `bedrock:Retrieve` permission
   - Knowledge bases are in the same region as the agent

3. **Check logs:**
   ```bash
   aws logs tail /aws/bedrock-agentcore/runtime/agent_* --follow
   ```

4. **Test KB directly:**
   ```bash
   aws bedrock-agent-runtime retrieve \
     --knowledge-base-id $NATIONAL_KB_ID \
     --retrieval-query text="test query"
   ```
