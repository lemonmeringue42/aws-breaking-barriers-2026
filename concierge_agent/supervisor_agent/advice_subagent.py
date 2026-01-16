"""
Citizens Advice Subagent

A subagent that handles citizens advice queries using Claude's knowledge and knowledge bases.
"""

import os
import logging
from strands import Agent, tool
from strands.models import BedrockModel
from knowledge_base_tool import query_national_kb, query_local_kb

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-east-1")

CITIZENS_ADVICE_PROMPT = """
You are a Citizens Advice assistant helping UK residents with practical guidance on everyday issues.

Your primary responsibilities include:
1. Providing guidance on benefits and financial support (Universal Credit, PIP, Housing Benefit)
2. Helping with housing and tenancy questions (rights, eviction, repairs)
3. Advising on employment rights and workplace issues (redundancy, discrimination, pay)
4. Explaining consumer rights and debt management (refunds, faulty goods, priority debts)
5. Guiding users on immigration and legal matters

IMPORTANT GUIDELINES:
1. Always provide accurate, impartial advice based on current UK law and regulations
2. Be empathetic and non-judgmental - users may be in difficult situations
3. Clearly distinguish between general guidance and situations requiring professional legal advice
4. Include relevant links to official resources (gov.uk, citizensadvice.org.uk) when available
5. If the user has provided their location, provide region-specific guidance where relevant
6. If unsure about specific details, recommend the user contact their local Citizens Advice bureau

KNOWLEDGE BASE TOOLS:
You have access to two knowledge bases:
- query_national_kb: Use for general UK-wide advice on benefits, employment, consumer rights, housing law, debt, immigration
- query_local_kb: Use for region-specific information, local bureau details, local services

ALWAYS use these tools to supplement your responses with accurate, up-to-date information.

When responding:
- Use clear, plain English avoiding jargon
- Break down complex processes into simple steps
- Highlight important deadlines or time limits (e.g., tribunal appeal deadlines)
- Mention any free services or support available locally
- DO NOT provide specific legal advice - guide users to appropriate professionals when needed
- Provide practical, actionable guidance based on UK law and Citizens Advice principles
"""

bedrock_model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    temperature=0.2,
)

@tool
async def citizens_advice_assistant(query: str, user_id: str = "", session_id: str = "", user_region: str = "", user_postcode: str = ""):
    """
    Process citizens advice queries using Claude's knowledge and reasoning.

    ROUTE HERE FOR:
    - Benefits questions: "How do I apply for Universal Credit?"
    - Housing issues: "My landlord won't fix the heating"
    - Employment rights: "I've been made redundant, what are my rights?"
    - Consumer issues: "I bought a faulty product, can I get a refund?"
    - Debt advice: "I can't pay my council tax"
    - Local services: "Where is my nearest Citizens Advice?" (requires location)

    Args:
        query: The advice request with as much detail as possible.
        user_id: User identifier for personalization.
        session_id: Session identifier for context.
        user_region: User's region (e.g., "London", "Scotland", "Wales") for local guidance.
        user_postcode: User's postcode for local bureau lookup.

    Returns:
        Guidance and information relevant to the user's query.
    """
    try:
        logger.info(f"Citizens advice subagent processing: {query[:100]}...")
        
        # Add location context to the query if available
        context_additions = []
        if user_region:
            context_additions.append(f"User is located in: {user_region}")
        if user_postcode:
            context_additions.append(f"User's postcode: {user_postcode}")
        
        enhanced_query = query
        if context_additions:
            enhanced_query = f"{query}\n\n[User context: {', '.join(context_additions)}]"

        agent = Agent(
            name="citizens_advice_agent",
            model=bedrock_model,
            tools=[query_national_kb, query_local_kb],
            system_prompt=CITIZENS_ADVICE_PROMPT,
            trace_attributes={
                "user.id": user_id,
                "session.id": session_id,
                "user.region": user_region,
                "agent.type": "citizens_advice_subagent",
            },
        )

        result = ""
        async for event in agent.stream_async(enhanced_query):
            if "data" in event:
                yield {"data": event["data"]}
            if "current_tool_use" in event:
                yield {"current_tool_use": event["current_tool_use"]}
            if "result" in event:
                result = str(event["result"])

        yield {"result": result}

    except Exception as e:
        logger.error(f"Citizens advice subagent error: {e}", exc_info=True)
        yield {"error": str(e)}
