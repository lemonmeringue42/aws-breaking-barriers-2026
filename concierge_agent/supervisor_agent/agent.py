import os
import logging
import boto3
import datetime
import json
import traceback
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from dynamodb_manager import DynamoDBManager
from gateway_client import get_gateway_client, call_mcp_tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
app.cors_allow_origins = ["http://localhost:3000", "http://localhost:5173"]
app.cors_allow_methods = ["GET", "POST", "OPTIONS"]
app.cors_allow_headers = ["Content-Type", "Authorization"]

REGION = os.getenv("AWS_REGION", "us-west-2")
MEMORY_ID = os.getenv("MEMORY_ID")

# Initialize Claude
llm = ChatBedrock(
    model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    region_name=REGION,
    model_kwargs={"temperature": 0.1, "max_tokens": 4096}
)

# Tool definitions for Claude
TOOLS = [
    {
        "name": "query_knowledge_base",
        "description": "Search Citizens Advice knowledge base for guidance on benefits, housing, employment, consumer rights, debt, immigration. Use for any factual questions about UK law and rights.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "kb_type": {"type": "string", "enum": ["national", "local"], "description": "national for UK-wide guidance, local for region-specific info"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "save_case_notes",
        "description": "Save case notes for the user. Call this when user provides case details, books appointment, or conversation contains important information to remember.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The case notes content to save"},
                "category": {"type": "string", "description": "Issue category: benefits, housing, debt, employment, consumer, immigration, general"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "get_case_notes",
        "description": "Retrieve saved case notes for the user.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "book_appointment",
        "description": "Book a callback appointment with an advisor. Use when user wants to speak to someone or needs human support.",
        "input_schema": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "User's phone number for callback"},
                "slot_number": {"type": "integer", "description": "Selected slot (1-6)"},
                "reason": {"type": "string", "description": "Brief reason for appointment"}
            },
            "required": ["phone", "slot_number"]
        }
    },
    {
        "name": "find_local_services",
        "description": "Find local support services by postcode - Citizens Advice bureaus, food banks, debt advice, housing support.",
        "input_schema": {
            "type": "object",
            "properties": {
                "postcode": {"type": "string", "description": "UK postcode"},
                "service_type": {"type": "string", "description": "Type: citizens_advice, food_bank, debt_advice, housing, legal_aid"}
            },
            "required": ["postcode"]
        }
    },
    {
        "name": "generate_letter",
        "description": "Generate a formal letter for the user - benefit appeals, landlord complaints, debt negotiation, employer grievances.",
        "input_schema": {
            "type": "object",
            "properties": {
                "letter_type": {"type": "string", "enum": ["benefit_appeal", "landlord_complaint", "debt_negotiation", "employer_grievance", "consumer_complaint"]},
                "details": {"type": "string", "description": "Key details to include in the letter"},
                "recipient_name": {"type": "string", "description": "Name of recipient"},
                "recipient_address": {"type": "string", "description": "Address of recipient"}
            },
            "required": ["letter_type", "details"]
        }
    }
]

SYSTEM_PROMPT = f"""You are Ally, a Citizens Advice assistant helping UK residents. Today is {datetime.datetime.now().strftime("%B %d, %Y")}.

CRISIS RESPONSE - If user mentions suicidal thoughts, domestic violence, homelessness tonight, or immediate danger:
Immediately provide: 🆘 Emergency: 999 | Samaritans: 116 123 | Domestic Abuse: 0808 2000 247 | Shelter: 0808 800 4444

YOUR TOOLS:
- query_knowledge_base: Search for guidance on benefits, housing, employment, debt, consumer rights
- save_case_notes: Save important case information (ALWAYS save after booking or when user shares case details)
- get_case_notes: Retrieve user's saved notes
- book_appointment: Book advisor callback (show slots 1-6, then book when user selects)
- find_local_services: Find nearby support by postcode
- generate_letter: Create formal letters (appeals, complaints, negotiations)

GUIDELINES:
- Use tools proactively - search KB for factual questions, save notes when user shares details
- Offer booking when user is distressed, has complex issues, or asks to speak to someone
- Use "we" and "our" when referring to Citizens Advice
- Be empathetic, use plain language, highlight deadlines
- Respond in the user's language

BOOKING FLOW:
1. When user wants appointment, show available slots (Mon-Fri, 9am-5pm, 30min intervals)
2. When user picks slot + gives phone, call book_appointment
3. After booking, ask for case details and save them with save_case_notes

IMPORTANT: Always save case notes when user provides substantive information about their situation."""


def get_user_profile(user_id: str) -> str:
    """Get user profile data."""
    try:
        manager = DynamoDBManager(region_name=REGION)
        profile = manager.get_user_profile(user_id)
        if profile:
            parts = []
            if profile.get("name"): parts.append(f"Name: {profile['name']}")
            if profile.get("address"): parts.append(f"Address: {profile['address']}")
            return f"User ID: {user_id}, " + ", ".join(parts) if parts else f"User ID: {user_id}"
    except Exception as e:
        logger.warning(f"Could not get profile: {e}")
    return f"User ID: {user_id}"


def get_long_term_memory(user_id: str, query: str) -> str:
    """Retrieve long-term memories."""
    if not MEMORY_ID:
        return ""
    try:
        client = boto3.client("bedrock-agentcore", region_name=REGION)
        memories = []
        
        # Use wildcard namespace to search all user memories
        response = client.retrieve_memory_records(
            memoryId=MEMORY_ID,
            namespace=f"/users/{user_id}/*",
            searchCriteria={"searchQuery": query, "topK": 10}
        )
        for record in response.get("memoryRecordSummaries", []):
            content = record.get("content", {}).get("text", "")
            if content:
                memories.append(content)
        
        return "\n".join(memories) if memories else ""
    except Exception as e:
        logger.debug(f"Memory retrieval failed: {e}")
        return ""


def execute_tool(tool_name: str, tool_input: dict, user_id: str, session_id: str) -> str:
    """Execute a tool and return result."""
    logger.info(f"🔧 Executing tool: {tool_name} with input: {tool_input}")
    
    try:
        if tool_name == "query_knowledge_base":
            from knowledge_base_tool import query_national_kb, query_local_kb
            kb_type = tool_input.get("kb_type", "national")
            query = tool_input.get("query", "")
            if kb_type == "local":
                return query_local_kb(query) or "No local results found."
            return query_national_kb(query) or "No results found."
        
        elif tool_name == "save_case_notes":
            content = tool_input.get("content", "")
            category = tool_input.get("category", "general")
            result = call_mcp_tool("create_note", {
                "user_id": user_id,
                "content": content,
                "category": category,
                "action_required": False
            })
            return f"Case notes saved successfully." if "error" not in result.lower() else result
        
        elif tool_name == "get_case_notes":
            result = call_mcp_tool("get_notes", {"user_id": user_id})
            return result if result else "No case notes found."
        
        elif tool_name == "book_appointment":
            from datetime import datetime, timedelta
            import uuid
            
            phone = tool_input.get("phone", "")
            slot_num = tool_input.get("slot_number", 1)
            reason = tool_input.get("reason", "General advice")
            
            # Generate slot display
            slots = []
            now = datetime.now()
            for day_offset in range(1, 6):
                date = now + timedelta(days=day_offset)
                if date.weekday() >= 5: continue
                for hour in range(9, 17):
                    for minute in [0, 30]:
                        slot_time = date.replace(hour=hour, minute=minute, second=0)
                        slots.append(slot_time.strftime("%A %d %B at %H:%M"))
            
            slot_display = slots[slot_num - 1] if 1 <= slot_num <= len(slots) else slots[0]
            ref = f"CA-{uuid.uuid4().hex[:6].upper()}"
            
            # Save booking as case note
            call_mcp_tool("create_note", {
                "user_id": user_id,
                "content": f"BOOKING: {ref}\nAppointment: {slot_display}\nPhone: {phone}\nReason: {reason}",
                "category": "booking",
                "action_required": True
            })
            
            return f"✅ Appointment booked!\nReference: {ref}\nTime: {slot_display}\nWe'll call: {phone}"
        
        elif tool_name == "find_local_services":
            from local_services_tool import find_local_services
            postcode = tool_input.get("postcode", "")
            service_type = tool_input.get("service_type", "citizens_advice")
            return find_local_services(postcode, service_type) or "No services found for that postcode."
        
        elif tool_name == "generate_letter":
            from document_generator_tool import generate_letter
            return generate_letter(
                letter_type=tool_input.get("letter_type", "general"),
                user_id=user_id,
                details=tool_input.get("details", ""),
                recipient_name=tool_input.get("recipient_name", ""),
                recipient_address=tool_input.get("recipient_address", "")
            )
        
        else:
            return f"Unknown tool: {tool_name}"
            
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return f"Tool error: {str(e)}"


@app.entrypoint
async def agent_stream(payload):
    """Main entrypoint - simple tool-calling agent."""
    user_query = payload.get("prompt", "")
    user_id = payload.get("user_id", "")
    session_id = payload.get("session_id", "")

    logger.info(f"=== AGENT REQUEST ===")
    logger.info(f"Query: {user_query[:100]}...")

    if not all([user_query, user_id, session_id]):
        yield {"status": "error", "error": "Missing required fields"}
        return

    try:
        # Build context
        user_profile = get_user_profile(user_id)
        memory = get_long_term_memory(user_id, user_query)
        
        context = f"USER: {user_profile}"
        if memory:
            context += f"\n\nPREVIOUS CONTEXT:\n{memory}"
        
        messages = [
            {"role": "user", "content": f"{context}\n\nUser message: {user_query}"}
        ]
        
        tools_used = []
        max_iterations = 10
        
        for iteration in range(max_iterations):
            logger.info(f"Iteration {iteration + 1}")
            
            # Call Claude with tools
            response = llm.invoke(
                [SystemMessage(content=SYSTEM_PROMPT)] + [
                    HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"])
                    for m in messages
                ],
                tools=TOOLS
            )
            
            # Check for tool calls
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_input = tool_call["args"]
                    
                    tools_used.append(tool_name)
                    
                    # Emit tool use event
                    yield {
                        "event": {
                            "contentBlockStart": {
                                "start": {
                                    "toolUse": {
                                        "name": tool_name,
                                        "toolUseId": tool_call.get("id", tool_name)
                                    }
                                },
                                "contentBlockIndex": len(tools_used)
                            }
                        }
                    }
                    
                    # Execute tool
                    result = execute_tool(tool_name, tool_input, user_id, session_id)
                    logger.info(f"Tool result: {result[:200]}...")
                    
                    # Add tool result to messages
                    messages.append({"role": "assistant", "content": f"[Called {tool_name}]"})
                    messages.append({"role": "user", "content": f"Tool result for {tool_name}: {result}"})
                
                continue  # Loop to let Claude process tool results
            
            # No tool calls - stream final response
            final_content = response.content if isinstance(response.content, str) else str(response.content)
            
            # Emit message start
            yield {"event": {"messageStart": {"role": "assistant"}}}
            
            # Stream content in chunks
            chunk_size = 20
            for i in range(0, len(final_content), chunk_size):
                yield {
                    "event": {
                        "contentBlockDelta": {
                            "delta": {"text": final_content[i:i+chunk_size]},
                            "contentBlockIndex": 0
                        }
                    }
                }
            
            # Emit message stop
            yield {"event": {"messageStop": {"stopReason": "end_turn"}}}
            
            # Emit tool results for UI
            for tool_name in tools_used:
                yield {
                    "tool_stream_event": {
                        "tool_use": {"name": tool_name},
                        "data": {"result": "completed"}
                    }
                }
            
            break  # Done
            
    except Exception as e:
        logger.error(f"Agent error: {e}")
        logger.error(traceback.format_exc())
        yield {"event": {"contentBlockDelta": {"delta": {"text": f"I encountered an error. Please try again."}}}}
        yield {"event": {"messageStop": {"stopReason": "end_turn"}}}


if __name__ == "__main__":
    app.run()
