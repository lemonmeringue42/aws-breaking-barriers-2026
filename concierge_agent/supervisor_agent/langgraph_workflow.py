"""
LangGraph Workflow for Citizens Advice Agent
Structured conversation flow with conditional routing based on urgency.
"""

import os
import logging
from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Import existing tools
from triage_tool import classify_and_route_case
from local_services_tool import find_local_services
from document_generator_tool import generate_letter
from booking_tool import get_booking_slots, book_appointment

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-west-2")
MEMORY_ID = os.getenv("MEMORY_ID")

# MCP Notes client (lazy loaded)
_mcp_client = None

def get_notes_mcp_client():
    """Get or create MCP client for Notes tools."""
    global _mcp_client
    if _mcp_client is None:
        try:
            from gateway_client import get_gateway_client
            _mcp_client = get_gateway_client(r"^notestools___", prefix="notes")
            logger.info("✅ MCP Notes client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize MCP client: {e}")
    return _mcp_client


def call_mcp_tool(tool_name: str, args: dict) -> str:
    """Call an MCP tool through the gateway."""
    try:
        client = get_notes_mcp_client()
        if not client:
            return "MCP client not available"
        
        # Find the tool
        tools = client.list_tools_sync()
        for tool in tools:
            if tool_name in tool.name:
                result = client.call_tool_sync(tool.name, args)
                return str(result)
        return f"Tool {tool_name} not found"
    except Exception as e:
        logger.error(f"MCP tool call failed: {e}")
        return f"Error: {e}"


# Define state
class ConversationState(TypedDict):
    messages: list
    user_id: str
    session_id: str
    issue_category: str | None
    urgency_level: str | None
    details_collected: dict
    next_action: str | None
    case_logged: bool
    long_term_memory: str | None  # Added for memory context
    tools_used: list  # Track tools used for UI display


# Initialize Claude model
llm = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    model_kwargs={"temperature": 0.1, "max_tokens": 2000}
)


def retrieve_long_term_memory(user_id: str, query: str) -> str:
    """Retrieve relevant long-term memories for the user."""
    if not MEMORY_ID:
        logger.warning("MEMORY_ID not set - skipping memory retrieval")
        return ""
    try:
        import boto3
        client = boto3.client("bedrock-agentcore", region_name=REGION)
        memories = []
        
        logger.info(f"🧠 Retrieving memory for user {user_id}, query: {query[:50]}...")
        
        # Semantic search for relevant facts - use wildcard namespace pattern
        try:
            response = client.retrieve_memory_records(
                memoryId=MEMORY_ID,
                namespace=f"/users/{user_id}/*",
                searchCriteria={"searchQuery": query, "topK": 10}
            )
            for record in response.get("memoryRecordSummaries", []):
                content = record.get("content", {}).get("text", "")
                if content:
                    memories.append(content)
            logger.info(f"📚 Found {len(response.get('memoryRecordSummaries', []))} memories via semantic search")
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
        
        # Also try listing recent records from summaries namespace
        try:
            response = client.list_memory_records(
                memoryId=MEMORY_ID,
                namespace=f"/users/{user_id}/*"
            )
            for record in response.get("memoryRecordSummaries", [])[:5]:
                content = record.get("content", {}).get("text", "")
                if content and content not in memories:
                    memories.append(content)
            logger.info(f"📋 Found {len(response.get('memoryRecordSummaries', []))} records via list")
        except Exception as e:
            logger.warning(f"List records failed: {e}")
        
        if memories:
            logger.info(f"✅ Retrieved {len(memories)} memory items total")
        else:
            logger.info("ℹ️ No previous memories found for this user")
        
        return "\n".join(memories) if memories else ""
    except Exception as e:
        logger.error(f"Memory retrieval error: {e}")
        return ""


def identify_issue_node(state: ConversationState) -> ConversationState:
    """Identify the type of issue the user is facing."""
    logger.info("🔍 Node: Identify Issue")
    
    messages = state["messages"]
    user_id = state["user_id"]
    
    # Retrieve long-term memory for context
    user_query = messages[-1].content if messages else ""
    user_query_lower = user_query.lower()
    
    # Check if user is providing case details after booking (look for "that's all" or case info)
    ai_messages = [m.content for m in messages if isinstance(m, AIMessage)]
    last_ai = ai_messages[-1] if ai_messages else ""
    
    # Priority: If user says "that's all" with case details, route to collect_case_details
    has_thats_all = "that's all" in user_query_lower or "thats all" in user_query_lower
    if has_thats_all:
        logger.info("📝 Detected 'that's all' - routing to collect_case_details")
        state["issue_category"] = "case_details"
        state["urgency_level"] = "STANDARD"
        state["details_collected"] = state.get("details_collected", {})
        state["details_collected"]["case_notes"] = user_query.replace("that's all", "").replace("That's all", "").strip()
        return state
    
    if "Building Your Case File" in last_ai or "case file" in last_ai.lower():
        logger.info("📝 Detected case details input - routing to collect_case_details")
        state["issue_category"] = "case_details"
        state["urgency_level"] = "STANDARD"
        return state
    
    # Check if user wants to generate a letter
    # Direct requests: "write a letter to X", "draft a letter", etc.
    direct_letter_request = ("write a letter" in user_query_lower or "draft a letter" in user_query_lower or 
                             "create a letter" in user_query_lower or "generate a letter" in user_query_lower)
    # Follow-up requests after discussion
    followup_keywords = ["create the letter", "generate the letter", "write the letter", "draft the letter", 
                        "yes, write", "yes please", "create it", "generate it", "write it"]
    wants_followup = any(kw in user_query_lower for kw in followup_keywords)
    offered_letter = "letter" in last_ai.lower() and ("generate" in last_ai.lower() or "draft" in last_ai.lower() or "help you" in last_ai.lower())
    
    if direct_letter_request or (wants_followup and offered_letter):
        logger.info("📝 Detected letter generation request - routing to generate_letter")
        state["issue_category"] = "generate_letter"
        state["urgency_level"] = "STANDARD"
        return state
    
    # Check if this is a booking confirmation (slot number + phone)
    import re
    slot_match = re.search(r'\b([1-6])\b', user_query_lower)
    phone_match = re.search(r'(07\d{9}|07\d{3}\s?\d{6}|\d{11})', user_query.replace(' ', ''))
    
    if slot_match and phone_match:
        logger.info("📅 Detected booking confirmation - routing to booking")
        state["issue_category"] = "booking_confirmation"
        state["urgency_level"] = "STANDARD"
        # Store the slot and phone for booking node
        state["details_collected"] = state.get("details_collected", {})
        state["details_collected"]["selected_slot_num"] = int(slot_match.group(1))
        state["details_collected"]["phone"] = phone_match.group(1)
        return state
    
    # Check if user is asking about memory/previous conversations
    memory_keywords = ["remember", "previous", "last time", "before", "earlier", "history", "past conversation"]
    is_memory_query = any(kw in user_query_lower for kw in memory_keywords)
    
    # Check if user is asking for case notes
    notes_keywords = ["case notes", "my notes", "view notes", "show notes", "fetch notes", "get notes"]
    is_notes_query = any(kw in user_query_lower for kw in notes_keywords)
    
    if is_notes_query:
        logger.info("📋 Notes query detected")
        state["issue_category"] = "fetch_notes"
        state["urgency_level"] = "GENERAL"
        return state
    
    # Always retrieve long-term memory
    ltm = retrieve_long_term_memory(user_id, user_query)
    state["long_term_memory"] = ltm
    if ltm:
        logger.info(f"📚 Retrieved long-term memory: {len(ltm)} chars")
    
    # If user asks about memory, respond with what we know
    if is_memory_query:
        logger.info("🧠 Memory query detected")
        state["issue_category"] = "memory_recall"
        state["urgency_level"] = "GENERAL"
        return state
    
    memory_context = f"\n\nLONG-TERM MEMORY (previous sessions):\n{ltm}" if ltm else ""
    
    system_prompt = f"""You are a Citizens Advice assistant. Analyze the user's message and identify:
1. Issue category: mental_health, domestic_abuse, eviction, benefits, employment, debt, housing, consumer, immigration
2. Urgency indicators: suicidal thoughts, domestic violence, immediate eviction, no food/heating
{memory_context}
Respond in JSON format:
{{
  "issue_category": "category_name",
  "urgency_indicators": ["indicator1", "indicator2"],
  "needs_more_info": true/false
}}"""
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        *messages
    ])
    
    # Parse response (simplified - in production use structured output)
    content = response.content
    
    # CRISIS detection - only for actual crisis keywords in USER's message
    crisis_keywords = ["suicidal", "suicide", "kill myself", "end my life", "self-harm", 
                       "domestic violence", "being abused", "partner hit", "homeless tonight",
                       "no food", "starving", "bailiffs today", "bailiffs tomorrow"]
    
    is_crisis = any(keyword in user_query_lower for keyword in crisis_keywords)
    
    # Extract issue category based on LLM response and user query
    if is_crisis and ("suicid" in user_query_lower or "self-harm" in user_query_lower or "kill myself" in user_query_lower):
        state["issue_category"] = "mental_health"
        state["urgency_level"] = "CRISIS"
    elif is_crisis and ("domestic" in user_query_lower or "abuse" in user_query_lower or "hit me" in user_query_lower):
        state["issue_category"] = "domestic_abuse"
        state["urgency_level"] = "CRISIS"
    elif is_crisis:
        state["issue_category"] = "crisis"
        state["urgency_level"] = "CRISIS"
    elif "evict" in user_query_lower and ("tomorrow" in user_query_lower or "today" in user_query_lower):
        state["issue_category"] = "eviction"
        state["urgency_level"] = "URGENT"
    elif "evict" in user_query_lower:
        state["issue_category"] = "eviction"
        state["urgency_level"] = "STANDARD"
    elif "benefit" in user_query_lower or "universal credit" in user_query_lower or "pip" in user_query_lower:
        state["issue_category"] = "benefits"
        state["urgency_level"] = "STANDARD"
    elif "debt" in user_query_lower:
        state["issue_category"] = "debt"
        state["urgency_level"] = "STANDARD"
    elif "landlord" in user_query_lower or "housing" in user_query_lower or "tenant" in user_query_lower:
        state["issue_category"] = "housing"
        state["urgency_level"] = "STANDARD"
    elif "job" in user_query_lower or "employer" in user_query_lower or "work" in user_query_lower:
        state["issue_category"] = "employment"
        state["urgency_level"] = "STANDARD"
    elif "local" in user_query_lower or "support" in user_query_lower or "services" in user_query_lower:
        state["issue_category"] = "local_services"
        state["urgency_level"] = "GENERAL"
    else:
        state["issue_category"] = "general"
        state["urgency_level"] = "GENERAL"
    
    logger.info(f"Identified: {state['issue_category']} - {state['urgency_level']}")
    
    return state


def generate_letter_node(state: ConversationState) -> ConversationState:
    """Generate a letter using the document generator tool."""
    logger.info("📝 Node: Generate Letter")
    
    from document_generator_tool import generate_letter
    import re
    
    user_text = " ".join([m.content for m in state["messages"] if isinstance(m, HumanMessage)])
    all_lower = user_text.lower()
    
    # Determine letter type
    letter_type = "landlord_complaint"
    if " mp " in all_lower or "my mp" in all_lower or "member of parliament" in all_lower:
        letter_type = "mp_letter"
    elif "benefit" in all_lower or "pip" in all_lower or "universal credit" in all_lower:
        letter_type = "benefit_appeal"
    elif "employer" in all_lower and "grievance" in all_lower:
        letter_type = "employer_grievance"
    elif "debt" in all_lower or "creditor" in all_lower:
        letter_type = "debt_negotiation"
    elif "refund" in all_lower or "faulty" in all_lower:
        letter_type = "consumer_complaint"
    
    kwargs = {}
    
    # Extract name
    name_match = re.search(r'(?:my name is|name:)\s*([A-Z][a-z]+\s+[A-Z][a-z]+)', user_text)
    if name_match:
        kwargs["user_name"] = name_match.group(1)
    
    # Extract address - simpler pattern
    addr_match = re.search(r'(?:I live at|live at|address:)\s*(.+?(?:[A-Z]{1,2}\d+\s*\d[A-Z]{2}))', user_text)
    if addr_match:
        kwargs["user_address"] = addr_match.group(1).strip()
    
    # Letter-specific extraction
    if letter_type == "mp_letter":
        kwargs["subject"] = "Affordable Housing Crisis" if "housing" in all_lower else "Local Concern"
        kwargs["issue_category"] = "housing" if "housing" in all_lower else "local issue"
        
        # Build issue description from user's words
        issues = []
        wait_match = re.search(r'(\d+)\s*years?.*waiting list', user_text, re.I)
        if wait_match:
            issues.append(f"I have been on the council housing waiting list for {wait_match.group(1)} years")
        rent_match = re.search(r'rents?.*(?:increased|risen).*?(\d+%)', user_text, re.I)
        if rent_match:
            issues.append(f"Private rents have increased by {rent_match.group(1)} in my area")
        kwargs["issue_description"] = ". ".join(issues) if issues else "There is a shortage of affordable housing"
        kwargs["impact_description"] = "This is causing hardship for local residents who cannot find affordable homes"
        
        # Extract requested action
        if "support" in all_lower and "social housing" in all_lower:
            kwargs["requested_action"] = "Support more social housing development in our area"
        else:
            kwargs["requested_action"] = "Raise this issue and advocate for solutions"
        kwargs["background_info"] = "Many constituents are affected by this issue"
        
    elif letter_type == "landlord_complaint":
        # Extract issue type
        if "heating" in all_lower:
            kwargs["issue_type"] = "heating system failure"
            kwargs["issue_description"] = "The heating system is not working"
            kwargs["specific_obligations"] = "maintaining the heating system in good working order"
        elif "damp" in all_lower or "mould" in all_lower:
            kwargs["issue_type"] = "damp and mould"
            kwargs["issue_description"] = "There is damp and mould in the property"
            kwargs["specific_obligations"] = "keeping the property free from damp"
        else:
            kwargs["issue_type"] = "repair issue"
            kwargs["issue_description"] = "There are outstanding repairs needed"
            kwargs["specific_obligations"] = "maintaining the property in good repair"
        
        kwargs["impact_description"] = "This is affecting my ability to live comfortably in the property"
        kwargs["requested_action"] = "arrange for repairs to be carried out"
    
    try:
        result = generate_letter(
            letter_type=letter_type,
            user_name=kwargs.pop("user_name", "[Your Name]"),
            user_address=kwargs.pop("user_address", "[Your Address]"),
            **kwargs
        )
        state["messages"].append(AIMessage(content=result))
    except Exception as e:
        logger.error(f"Letter generation failed: {e}", exc_info=True)
        state["messages"].append(AIMessage(content="I encountered an error generating the letter. Please try again."))
    
    return state


def memory_recall_node(state: ConversationState) -> ConversationState:
    """Respond to user asking about previous conversations."""
    logger.info("🧠 Node: Memory Recall")
    
    ltm = state.get("long_term_memory", "")
    
    if ltm:
        response = f"""Yes, I remember some details from our previous conversations:

{ltm}

How can I help you today? Would you like to continue with any of these topics, or is there something new I can assist with?"""
    else:
        response = """I don't have any stored memories from previous conversations with you yet. This could be because:

- This is your first conversation with me
- Previous sessions haven't been saved to your profile yet

But don't worry - as we chat today, I'll remember key details for future sessions. How can I help you today?"""
    
    state["messages"].append(AIMessage(content=response))
    state["next_action"] = "end"
    
    return state


def fetch_notes_node(state: ConversationState) -> ConversationState:
    """Fetch and display case notes for the user."""
    logger.info("📋 Node: Fetch Notes")
    
    tools_used = state.get("tools_used", [])
    user_id = state["user_id"]
    
    try:
        tools_used.append("mcp_get_notes")
        notes_result = call_mcp_tool("get_notes", {"user_id": user_id})
        
        if notes_result and "not found" not in notes_result.lower() and "error" not in notes_result.lower():
            response = f"""📋 **Your Case Notes**

{notes_result}

---
Is there anything specific from these notes you'd like to discuss or update?"""
        else:
            response = """📋 **No case notes found**

I don't have any saved case notes for you yet. Notes are created when:
- You book an appointment
- An advisor logs information about your case
- You provide case details during our conversation

How can I help you today?"""
    except Exception as e:
        logger.error(f"Error fetching notes: {e}")
        response = "I couldn't retrieve your case notes at the moment. Please try again later."
    
    state["tools_used"] = tools_used
    state["messages"].append(AIMessage(content=response))
    state["next_action"] = "end"
    
    return state


def crisis_response_node(state: ConversationState) -> ConversationState:
    """Provide immediate crisis support."""
    logger.info("🚨 Node: Crisis Response")
    
    crisis_message = """I'm very concerned about your safety and wellbeing. Please contact these services immediately:

🆘 **EMERGENCY**: If you're in immediate danger, call **999**

**Mental Health Crisis:**
- Samaritans: **116 123** (24/7, free)
- Crisis text line: Text **SHOUT** to **85258**

**Domestic Abuse:**
- National Domestic Abuse Helpline: **0808 2000 247** (24/7)

**Homelessness:**
- Shelter Emergency Helpline: **0808 800 4444**

I'm logging your case as urgent so one of our advisors can contact you as soon as possible. In the meantime, please reach out to these services for immediate support."""
    
    state["messages"].append(AIMessage(content=crisis_message))
    state["next_action"] = "triage"
    
    return state


def gather_details_node(state: ConversationState) -> ConversationState:
    """Gather necessary details about the issue - or skip if enough info provided."""
    logger.info("📋 Node: Gather Details")
    
    issue = state["issue_category"]
    user_message = state["messages"][-1].content if state["messages"] else ""
    
    # Check if user already provided substantial detail (more than 50 chars suggests context)
    has_detail = len(user_message) > 50
    
    # Check for specific keywords that indicate user wants action, not questions
    action_keywords = ["book", "appointment", "callback", "speak to", "write a letter", 
                       "generate", "create", "find", "nearest", "local", "help me with"]
    wants_action = any(kw in user_message.lower() for kw in action_keywords)
    
    # Skip gathering if user provided detail or wants immediate action
    if has_detail or wants_action:
        logger.info("Skipping gather_details - user provided enough context")
        state["next_action"] = "provide_guidance"
        return state
    
    # Check for money worries - add essentials check
    user_lower = user_message.lower()
    needs_essentials_check = any(kw in user_lower for kw in ["money", "debt", "bills", "afford", "struggling", "desperate"])
    
    questions = {
        "eviction": "Can you tell me more about your eviction situation? When did you receive the notice?",
        "benefits": "Which benefit are you asking about? Are you currently receiving any benefits?",
        "debt": "What type of debt are you dealing with? Do you know the total amount owed?\n\nAlso, can I quickly check you've got the essentials covered—food, toiletries, and any medication?",
        "housing": "What's the specific issue with your housing?",
        "employment": "Can you describe the workplace issue? Have you raised this with your employer?",
    }
    
    question = questions.get(issue)
    
    # Add essentials check for money-related issues
    if question and needs_essentials_check and "essentials" not in question:
        question += "\n\nAlso, can I quickly check you've got the essentials covered—food, toiletries, and any medication?"
    
    # Only ask if we have a specific question for this category
    if question:
        state["messages"].append(AIMessage(content=question))
    
    state["next_action"] = "provide_guidance"
    
    return state


def provide_guidance_node(state: ConversationState) -> ConversationState:
    """Provide tailored guidance based on the issue, using knowledge base."""
    logger.info("💡 Node: Provide Guidance")
    
    messages = state["messages"]
    issue = state["issue_category"]
    ltm = state.get("long_term_memory", "")
    user_query = messages[-1].content if messages else ""
    
    # Track tools used
    tools_used = state.get("tools_used", [])
    
    # Query knowledge base for relevant information
    kb_context = ""
    try:
        from knowledge_base_tool import query_national_kb, query_local_kb
        
        # Query national KB for general guidance
        logger.info(f"🔧 Calling query_national_kb for: {issue}")
        tools_used.append("query_national_kb")
        kb_result = query_national_kb(f"{issue} {user_query[:100]}")
        if kb_result and "not configured" not in kb_result.lower():
            kb_context = f"\n\nKNOWLEDGE BASE RESULTS:\n{kb_result[:2000]}"
            logger.info(f"📚 KB returned {len(kb_result)} chars")
        
        # Check for location-specific queries
        location_keywords = ["near", "local", "birmingham", "london", "manchester", "croydon", "postcode"]
        if any(kw in user_query.lower() for kw in location_keywords):
            logger.info(f"🔧 Calling query_local_kb for location query")
            tools_used.append("query_local_kb")
            local_result = query_local_kb(user_query[:200])
            if local_result and "not configured" not in local_result.lower():
                kb_context += f"\n\nLOCAL INFORMATION:\n{local_result[:1000]}"
    except Exception as e:
        logger.warning(f"KB query failed: {e}")
    
    state["tools_used"] = tools_used
    
    memory_context = f"\n\nLONG-TERM MEMORY (use for personalization):\n{ltm}" if ltm else ""
    
    system_prompt = f"""You are a Citizens Advice assistant. The user has a {issue} issue.
{memory_context}
Provide clear, practical guidance:
1. Explain their rights under UK law
2. Outline the steps they should take
3. Mention any deadlines or time limits
4. Suggest what tools/services we can help with (local services, letter generation)
5. Reference any relevant context from previous sessions naturally

Keep it concise and actionable. Use plain English."""
    
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        *messages
    ])
    
    state["messages"].append(AIMessage(content=response.content))
    state["next_action"] = "offer_tools"
    
    return state


def offer_tools_node(state: ConversationState) -> ConversationState:
    """Offer relevant tools to the user, including booking if requested."""
    logger.info("🛠️ Node: Offer Tools")
    
    issue = state["issue_category"]
    urgency = state["urgency_level"]
    user_messages = " ".join([m.content.lower() for m in state["messages"] if isinstance(m, HumanMessage)])
    
    # Check if user explicitly asked for booking
    wants_booking = any(word in user_messages for word in ["book", "callback", "call me", "speak to", "advisor"])
    
    # Build the offer message
    tool_offers = {
        "eviction": "\n\n**How I can help further:**\n- 📍 Find emergency housing services near you\n- 📝 Generate a letter to your landlord\n- 📞 Book an urgent callback with an advisor",
        "benefits": "\n\n**How I can help further:**\n- 📍 Find local benefits advice services\n- 📝 Generate a benefit appeal letter\n- 📞 Book a callback with an advisor",
        "debt": "\n\n**How I can help further:**\n- 📍 Find debt advice services near you\n- 📝 Generate a debt negotiation letter\n- 📞 Book a callback with an advisor",
        "housing": "\n\n**How I can help further:**\n- 📍 Find local housing support\n- 📝 Generate a complaint letter to your landlord\n- 📞 Book a callback with an advisor",
        "employment": "\n\n**How I can help further:**\n- 📝 Generate a formal grievance letter\n- 📞 Book a callback with an advisor",
        "local_services": "\n\n**How I can help further:**\n- 📍 Find support services near you\n- 📞 Book a callback with an advisor",
    }
    
    offer = tool_offers.get(issue, "\n\n**How I can help further:**\n- 📍 Find your nearest Citizens Advice\n- 📞 Book a callback with an advisor")
    
    last_message = state["messages"][-1].content
    state["messages"][-1] = AIMessage(content=last_message + offer)
    
    # If user asked for booking, go to booking node next
    if wants_booking or urgency in ["CRISIS", "URGENT"]:
        state["next_action"] = "booking"
    else:
        state["next_action"] = "triage"
    
    return state


def route_after_tools(state: ConversationState) -> Literal["booking", "triage"]:
    """Route to booking if requested, otherwise triage."""
    if state.get("next_action") == "booking":
        return "booking"
    return "triage"


def store_conversation_to_memory(state: ConversationState) -> None:
    """Store conversation summary and facts to long-term memory."""
    if not MEMORY_ID:
        logger.warning("MEMORY_ID not set - skipping memory storage")
        return
    
    try:
        import boto3
        import uuid
        from datetime import datetime, timezone
        
        client = boto3.client("bedrock-agentcore", region_name=REGION)
        user_id = state["user_id"]
        session_id = state["session_id"]
        
        # Extract conversation content
        user_messages = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
        
        # Create detailed summary
        issue = state.get("issue_category", "general")
        urgency = state.get("urgency_level", "GENERAL")
        
        summary_parts = [
            f"Issue: {issue} (Urgency: {urgency})",
            f"User query: {user_messages[0][:200] if user_messages else 'N/A'}",
        ]
        
        details = state.get("details_collected", {})
        if details:
            for key, value in details.items():
                if key not in ["booking_slots"] and value:
                    summary_parts.append(f"{key}: {str(value)[:100]}")
        
        summary = " | ".join(summary_parts)
        now = datetime.now(timezone.utc)
        
        logger.info(f"💾 Storing memory for user {user_id}, session {session_id}")
        
        # Store records with required timestamp field
        try:
            records = [
                {
                    "requestIdentifier": str(uuid.uuid4()).replace("-", "")[:40],
                    "namespaces": [f"/users/{user_id}/sessions/{session_id}/summaries"],
                    "content": {"text": summary},
                    "timestamp": now
                },
                {
                    "requestIdentifier": str(uuid.uuid4()).replace("-", "")[:40],
                    "namespaces": [f"/users/{user_id}/facts"],
                    "content": {"text": f"On {now.strftime('%Y-%m-%d')}, user discussed {issue}. {user_messages[0][:150] if user_messages else ''}"},
                    "timestamp": now
                }
            ]
            response = client.batch_create_memory_records(memoryId=MEMORY_ID, records=records)
            success = len(response.get("successfulRecords", []))
            failed = len(response.get("failedRecords", []))
            logger.info(f"✅ Memory storage: {success} succeeded, {failed} failed")
            if failed > 0:
                for rec in response.get("failedRecords", []):
                    logger.error(f"❌ Failed record: {rec.get('errorMessage')}")
        except Exception as e:
            logger.error(f"❌ Failed to store memory: {e}")
        
    except Exception as e:
        logger.error(f"❌ Memory storage error: {e}")


def triage_node(state: ConversationState) -> ConversationState:
    """Log the case for follow-up and save notes via MCP."""
    logger.info("📊 Node: Triage")
    
    tools_used = state.get("tools_used", [])
    
    if state.get("case_logged"):
        return state
    
    # Extract summary from conversation
    user_messages = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
    summary = " ".join(user_messages[:2])[:200]  # First 2 messages, max 200 chars
    
    # Determine time sensitivity
    urgency = state["urgency_level"]
    issue = state.get("issue_category", "general")
    
    # Save case note via MCP Notes tool
    try:
        logger.info("🔧 Calling MCP: create_note")
        tools_used.append("mcp_create_note")
        
        note_result = call_mcp_tool("create_note", {
            "user_id": state["user_id"],
            "content": f"Case: {issue} ({urgency})\n\nSummary: {summary}",
            "category": issue,
            "action_required": urgency in ["CRISIS", "URGENT"],
        })
        logger.info(f"📝 MCP Note created: {note_result[:100] if note_result else 'N/A'}")
    except Exception as e:
        logger.warning(f"MCP note creation failed: {e}")
    
    state["tools_used"] = tools_used
    
    # Call triage tool
    try:
        logger.info(f"Logging case: {urgency} - {issue}")
        state["case_logged"] = True
        
        # Add confirmation message
        if urgency == "CRISIS":
            confirmation = "\n\n✅ Your case has been logged as **CRISIS** priority. An advisor will contact you as soon as possible."
        elif urgency == "URGENT":
            confirmation = "\n\n✅ Your case has been logged as **URGENT**. An advisor will contact you within 24-48 hours."
        else:
            confirmation = "\n\n✅ Your case has been logged. We'll be in touch if you need further support."
        
        last_message = state["messages"][-1].content
        state["messages"][-1] = AIMessage(content=last_message + confirmation)
        
    except Exception as e:
        logger.error(f"Triage error: {e}")
    
    # Store conversation to long-term memory
    store_conversation_to_memory(state)
    
    state["next_action"] = "end"
    
    return state


def booking_node(state: ConversationState) -> ConversationState:
    """Show available booking slots or confirm booking if slot selected."""
    logger.info("📅 Node: Booking")
    
    user_messages = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
    last_user_msg = user_messages[-1].lower() if user_messages else ""
    
    # Check if user is confirming a slot (has number and phone)
    import re
    slot_match = re.search(r'\b([1-6])\b', last_user_msg)
    phone_match = re.search(r'(\d{5}\s?\d{6}|\d{11}|07\d{3}\s?\d{6})', last_user_msg.replace(' ', ''))
    
    # If we have stored slots and user selected one
    stored_slots = state.get("details_collected", {}).get("booking_slots", [])
    
    if slot_match and phone_match and stored_slots:
        # User is confirming a booking
        slot_num = int(slot_match.group(1)) - 1
        phone = phone_match.group(1)
        
        if 0 <= slot_num < len(stored_slots):
            selected_slot = stored_slots[slot_num]
            
            # Generate booking reference
            import uuid
            booking_ref = f"CA-{uuid.uuid4().hex[:6].upper()}"
            
            # Store booking details
            state["details_collected"]["booking_confirmed"] = {
                "reference": booking_ref,
                "slot": selected_slot,
                "phone": phone
            }
            
            confirmation = f"""✅ **Appointment Confirmed!**

📋 **Reference:** {booking_ref}
📅 **Date & Time:** {selected_slot['display']}
📞 **We'll call:** {phone}

---

**To help our advisor prepare for your call, please share any details about your situation:**

- What's the main issue you need help with?
- Are there any deadlines or urgent dates?
- Do you have any documents or letters related to this?

*Your answers will be added to your case file so the advisor can help you more effectively.*

Just type your details below, or say "that's all" if you'd prefer to discuss everything on the call."""

            state["messages"].append(AIMessage(content=confirmation))
            state["next_action"] = "collect_case_details"
            return state
    
    # Otherwise, show available slots
    urgency = state.get("urgency_level", "STANDARD")
    
    try:
        from datetime import datetime, timedelta
        
        days = 2 if urgency in ["URGENT", "CRISIS"] else 5
        slots = []
        now = datetime.now()
        
        for day_offset in range(1, days + 1):
            date = now + timedelta(days=day_offset)
            if date.weekday() >= 5:
                continue
            for hour in range(9, 17):
                for minute in [0, 30]:
                    slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    slots.append({
                        "slot_id": slot_time.strftime('%Y%m%d_%H%M'),
                        "display": slot_time.strftime("%A %d %B at %H:%M")
                    })
        
        if not slots:
            state["messages"].append(AIMessage(content="No available slots found. Please call us directly at **0800 144 8848** (Monday-Friday, 9am-5pm)."))
        else:
            display_slots = slots[:6]
            
            booking_message = "**📅 I can book a callback for you. Here are available times:**\n\n"
            for i, slot in enumerate(display_slots, 1):
                booking_message += f"**{i}.** {slot['display']}\n"
            
            booking_message += "\n**To book:** Just reply with the number (e.g., '1') and your phone number.\n"
            booking_message += "\nExample: *'1, my number is 07700 900123'*"
            
            state["messages"].append(AIMessage(content=booking_message))
            state["details_collected"]["booking_slots"] = display_slots
            
    except Exception as e:
        logger.error(f"Booking error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        state["messages"].append(AIMessage(content="I'd like to book a callback for you. Please call us directly at **0800 144 8848** (Monday-Friday, 9am-5pm) to schedule an appointment with an advisor."))
    
    state["next_action"] = "end"
    return state


def booking_confirm_node(state: ConversationState) -> ConversationState:
    """Confirm a booking when user provides slot number and phone."""
    logger.info("📅 Node: Booking Confirm")
    
    from datetime import datetime, timedelta
    import uuid
    
    slot_num = state.get("details_collected", {}).get("selected_slot_num", 1)
    phone = state.get("details_collected", {}).get("phone", "your number")
    
    # Generate slots to match what was shown
    slots = []
    now = datetime.now()
    for day_offset in range(1, 6):
        date = now + timedelta(days=day_offset)
        if date.weekday() >= 5:
            continue
        for hour in range(9, 17):
            for minute in [0, 30]:
                slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slots.append({
                    "slot_id": slot_time.strftime('%Y%m%d_%H%M'),
                    "display": slot_time.strftime("%A %d %B at %H:%M")
                })
    
    # Get selected slot
    if 1 <= slot_num <= len(slots):
        selected_slot = slots[slot_num - 1]
    else:
        selected_slot = slots[0] if slots else {"display": "Thursday at 10:00"}
    
    # Generate booking reference
    booking_ref = f"CA-{uuid.uuid4().hex[:6].upper()}"
    
    # Format phone for display
    phone_display = phone
    if len(phone) == 11 and phone.startswith('07'):
        phone_display = f"{phone[:5]} {phone[5:]}"
    
    confirmation = f"""✅ **Appointment Confirmed!**

📋 **Reference:** {booking_ref}
📅 **Date & Time:** {selected_slot['display']}
📞 **We'll call:** {phone_display}

---

📁 **Building Your Case File**

An advisor will review your case file ahead of this call. Please share any relevant information to help them prepare:

- What's the main issue you need help with?
- Any key dates, deadlines, or reference numbers?
- Documents you have (bills, letters, notices)?

Just type your details below and I'll add them to your case file. When you're done, say **"that's all"** and I'll show you a summary."""

    state["messages"].append(AIMessage(content=confirmation))
    state["next_action"] = "collect_case_details"
    
    return state


def collect_case_details_node(state: ConversationState) -> ConversationState:
    """Collect additional case details after booking confirmation."""
    logger.info("📝 Node: Collect Case Details")
    
    tools_used = state.get("tools_used", [])
    user_messages = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
    last_user_msg = user_messages[-1] if user_messages else ""
    last_user_msg_lower = last_user_msg.lower()
    
    # Get booking info - check both locations
    booking_info = state.get("details_collected", {}).get("booking_confirmed", {})
    
    # If no booking_confirmed, build from what we have
    if not booking_info:
        from datetime import datetime, timedelta
        slot_num = state.get("details_collected", {}).get("selected_slot_num", 1)
        phone = state.get("details_collected", {}).get("phone", "on file")
        
        # Generate slot display
        slots = []
        now = datetime.now()
        for day_offset in range(1, 6):
            date = now + timedelta(days=day_offset)
            if date.weekday() >= 5:
                continue
            for hour in range(9, 17):
                for minute in [0, 30]:
                    slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    slots.append(slot_time.strftime("%A %d %B at %H:%M"))
        
        slot_display = slots[slot_num - 1] if 1 <= slot_num <= len(slots) else "your scheduled time"
        import uuid
        ref = f"CA-{uuid.uuid4().hex[:6].upper()}"
        booking_info = {"slot": {"display": slot_display}, "reference": ref, "phone": phone}
    
    # Check if user said "that's all"
    if "that's all" in last_user_msg_lower or "thats all" in last_user_msg_lower or "no more" in last_user_msg_lower or "done" in last_user_msg_lower:
        response = f"""📁 **Case File Complete**

---

**📋 CASE FILE SUMMARY**

**Appointment:** {booking_info.get('slot', {}).get('display', 'Scheduled')}
**Reference:** {booking_info.get('reference', 'N/A')}
**Callback Number:** {booking_info.get('phone', 'On file')}

**Case Notes:** No additional details provided

---

✅ Your case file has been saved. The advisor will review this before your call.

**Need to reschedule?** Quote reference: {booking_info.get('reference', 'N/A')}

We look forward to speaking with you!"""
    else:
        # User provided details - save and show case file
        case_notes = last_user_msg
        state["details_collected"]["case_notes"] = case_notes
        
        # Extract any conversation context
        all_user_msgs = [m.content for m in state["messages"] if isinstance(m, HumanMessage)]
        conversation_summary = " | ".join(all_user_msgs[-3:])[:500]  # Last 3 messages
        
        response = f"""📁 **Case File Complete**

---

**📋 CASE FILE SUMMARY**

**Appointment:** {booking_info.get('slot', {}).get('display', 'Scheduled')}
**Reference:** {booking_info.get('reference', 'N/A')}
**Callback Number:** {booking_info.get('phone', 'On file')}

**Case Notes:**
{case_notes}

**Conversation Context:**
{conversation_summary}

---

✅ Your case file has been saved and will be reviewed by the advisor before your call.

**Need to reschedule?** Quote reference: {booking_info.get('reference', 'N/A')}

We look forward to speaking with you!"""
    
    state["messages"].append(AIMessage(content=response))
    state["next_action"] = "end"
    
    # Save case notes via MCP
    try:
        tools_used.append("mcp_create_note")
        case_notes = state.get("details_collected", {}).get("case_notes", last_user_msg)
        note_content = f"""Booking: {booking_info.get('reference', 'N/A')}
Appointment: {booking_info.get('slot', {}).get('display', 'Scheduled')}
Phone: {booking_info.get('phone', 'On file')}

Case Details:
{case_notes}"""
        
        note_result = call_mcp_tool("create_note", {
            "user_id": state["user_id"],
            "content": note_content,
            "category": state.get("issue_category", "general"),
            "action_required": True,
        })
        logger.info(f"📝 Case note saved: {note_result[:100] if note_result else 'N/A'}")
    except Exception as e:
        logger.warning(f"MCP note creation failed: {e}")
    
    state["tools_used"] = tools_used
    
    # Store to memory
    store_conversation_to_memory(state)
    
    return state


def wants_booking_only(state: ConversationState) -> bool:
    """Check if user ONLY wants to book an appointment (not combined with other requests)."""
    user_messages = " ".join([m.content.lower() for m in state["messages"] if isinstance(m, HumanMessage)])
    
    # Check for booking intent
    booking_keywords = ["book a call", "book an appointment", "book callback", "schedule a call", "arrange a callback"]
    has_booking_intent = any(keyword in user_messages for keyword in booking_keywords)
    
    # Check if there's also a substantive issue mentioned
    issue_keywords = ["evict", "debt", "benefit", "housing", "landlord", "employer", "redundan", "pip", "universal credit", "homeless", "money"]
    has_issue = any(keyword in user_messages for keyword in issue_keywords)
    
    # Only route to booking if it's a simple booking request without other issues
    # If they have an issue AND want booking, process the issue first
    return has_booking_intent and not has_issue


def route_after_identify(state: ConversationState) -> Literal["crisis_response", "booking", "booking_confirm", "memory_recall", "fetch_notes", "collect_case_details", "generate_letter", "gather_details"]:
    """Route based on urgency level and user intent."""
    if state.get("issue_category") == "case_details":
        return "collect_case_details"
    if state.get("issue_category") == "generate_letter":
        return "generate_letter"
    if state.get("issue_category") == "booking_confirmation":
        return "booking_confirm"
    if state.get("issue_category") == "memory_recall":
        return "memory_recall"
    if state.get("issue_category") == "fetch_notes":
        return "fetch_notes"
    if state["urgency_level"] == "CRISIS":
        return "crisis_response"
    if wants_booking_only(state):
        return "booking"
    return "gather_details"


def route_after_crisis(state: ConversationState) -> Literal["booking"]:
    """After crisis response, offer to book urgent callback."""
    return "booking"


def route_after_details(state: ConversationState) -> Literal["provide_guidance"]:
    """Always provide guidance after gathering details."""
    return "provide_guidance"


def route_after_guidance(state: ConversationState) -> Literal["offer_tools"]:
    """Always offer tools after guidance."""
    return "offer_tools"


def route_after_tools(state: ConversationState) -> Literal["booking", "triage"]:
    """Route to booking if requested, otherwise triage."""
    if state.get("next_action") == "booking":
        return "booking"
    return "triage"


def route_after_booking(state: ConversationState) -> Literal["collect_case_details", "__end__"]:
    """Route to case details collection if booking confirmed."""
    if state.get("next_action") == "collect_case_details":
        return "collect_case_details"
    return "__end__"


def route_after_triage(state: ConversationState) -> Literal["__end__"]:
    """End after triage."""
    return "__end__"


# Build the graph
def create_workflow():
    """Create the LangGraph workflow."""
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("identify_issue", identify_issue_node)
    workflow.add_node("memory_recall", memory_recall_node)
    workflow.add_node("fetch_notes", fetch_notes_node)
    workflow.add_node("generate_letter", generate_letter_node)
    workflow.add_node("crisis_response", crisis_response_node)
    workflow.add_node("gather_details", gather_details_node)
    workflow.add_node("provide_guidance", provide_guidance_node)
    workflow.add_node("offer_tools", offer_tools_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("booking", booking_node)
    workflow.add_node("booking_confirm", booking_confirm_node)
    workflow.add_node("collect_case_details", collect_case_details_node)
    
    # Set entry point
    workflow.set_entry_point("identify_issue")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "identify_issue",
        route_after_identify,
        {
            "crisis_response": "crisis_response",
            "booking": "booking",
            "booking_confirm": "booking_confirm",
            "memory_recall": "memory_recall",
            "fetch_notes": "fetch_notes",
            "generate_letter": "generate_letter",
            "collect_case_details": "collect_case_details",
            "gather_details": "gather_details"
        }
    )
    
    # Memory recall goes to end
    workflow.add_edge("memory_recall", END)
    
    # Fetch notes goes to end
    workflow.add_edge("fetch_notes", END)
    
    # Generate letter goes to end
    workflow.add_edge("generate_letter", END)
    
    # Booking confirm goes to end (user will provide case details in next message)
    workflow.add_edge("booking_confirm", END)
    
    workflow.add_conditional_edges(
        "crisis_response",
        route_after_crisis,
        {"booking": "booking"}
    )
    
    workflow.add_conditional_edges(
        "booking",
        route_after_booking,
        {
            "collect_case_details": "collect_case_details",
            "__end__": END
        }
    )
    
    workflow.add_edge("collect_case_details", END)
    
    workflow.add_conditional_edges(
        "gather_details",
        route_after_details,
        {"provide_guidance": "provide_guidance"}
    )
    
    workflow.add_conditional_edges(
        "provide_guidance",
        route_after_guidance,
        {"offer_tools": "offer_tools"}
    )
    
    workflow.add_conditional_edges(
        "offer_tools",
        route_after_tools,
        {
            "booking": "booking",
            "triage": "triage"
        }
    )
    
    workflow.add_conditional_edges(
        "triage",
        route_after_triage,
        {"__end__": END}
    )
    
    return workflow.compile()


# Create compiled graph
graph = create_workflow()
