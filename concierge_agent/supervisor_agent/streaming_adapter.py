"""
Streaming Adapter for LangGraph to Bedrock Format
Converts LangGraph workflow output to Bedrock's streaming event format.
"""

import logging
from typing import AsyncGenerator, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)

# Map tool names to user-friendly descriptions
TOOL_DESCRIPTIONS = {
    "query_national_kb": "📚 Searching national knowledge base",
    "query_local_kb": "📍 Searching local knowledge base",
    "find_local_services": "🏢 Finding local services",
    "generate_letter": "📝 Generating letter",
    "classify_and_route_case": "📋 Logging case for follow-up",
    "get_booking_slots": "📅 Finding appointment slots",
    "book_appointment": "✅ Booking appointment",
    "mcp_create_note": "📝 MCP: Saving case notes",
    "mcp_get_notes": "📋 MCP: Retrieving notes",
    "mcp_search_notes": "🔍 MCP: Searching notes",
}


class LangGraphStreamingAdapter:
    """Adapter to convert LangGraph output to Bedrock streaming format."""
    
    @staticmethod
    async def stream_workflow_output(
        workflow_graph,
        initial_state: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute LangGraph workflow and stream output in Bedrock format.
        
        Args:
            workflow_graph: Compiled LangGraph workflow
            initial_state: Initial state for the workflow
            
        Yields:
            Bedrock-formatted streaming events
        """
        try:
            logger.info("Starting LangGraph workflow execution...")
            
            # Track which messages we've already sent
            sent_message_count = len([m for m in initial_state["messages"] if isinstance(m, HumanMessage)])
            emitted_tools = set()
            message_started = False
            
            # Execute workflow and stream intermediate states
            for state in workflow_graph.stream(initial_state):
                logger.info(f"Workflow state update: {list(state.keys())}")
                
                # Extract the actual state (stream returns dict with node name as key)
                node_name = list(state.keys())[0]
                current_state = state[node_name]
                
                # Check for actual tools used in state
                state_tools = current_state.get("tools_used", [])
                logger.info(f"Node {node_name} - tools_used: {state_tools}")
                
                # Emit tool events (these will be collected by frontend)
                for tool_name in state_tools:
                    if tool_name not in emitted_tools:
                        emitted_tools.add(tool_name)
                        tool_display = TOOL_DESCRIPTIONS.get(tool_name, f"🔧 {tool_name}")
                        logger.info(f"Emitting tool event for: {tool_display}")
                        # Emit tool use start event using contentBlockStart format
                        yield {
                            "event": {
                                "contentBlockStart": {
                                    "start": {
                                        "toolUse": {
                                            "name": tool_display,
                                            "toolUseId": f"tool-{tool_name}-{len(emitted_tools)}"
                                        }
                                    },
                                    "contentBlockIndex": len(emitted_tools)
                                }
                            }
                        }
                
                # Get new AI messages
                messages = current_state.get("messages", [])
                
                # Stream any new AI messages
                for i, message in enumerate(messages):
                    if i < sent_message_count:
                        continue  # Skip already sent messages
                    
                    if isinstance(message, AIMessage) and message.content:
                        logger.info(f"Streaming message from node: {node_name}")
                        
                        # Send message start event (only once)
                        if not message_started:
                            yield {
                                "event": {
                                    "messageStart": {
                                        "role": "assistant"
                                    }
                                }
                            }
                            message_started = True
                        
                        # Send content block start
                        yield {
                            "event": {
                                "contentBlockStart": {
                                    "start": {
                                        "text": ""
                                    },
                                    "contentBlockIndex": 0
                                }
                            }
                        }
                        
                        # Stream content in chunks
                        content = message.content
                        chunk_size = 20  # Smaller chunks for smoother streaming
                        
                        for j in range(0, len(content), chunk_size):
                            chunk = content[j:j+chunk_size]
                            yield {
                                "event": {
                                    "contentBlockDelta": {
                                        "delta": {
                                            "text": chunk
                                        },
                                        "contentBlockIndex": 0
                                    }
                                }
                            }
                        
                        # Send content block stop
                        yield {
                            "event": {
                                "contentBlockStop": {
                                    "contentBlockIndex": 0
                                }
                            }
                        }
                        
                        sent_message_count += 1
            
            # Send message stop event with tools used
            yield {
                "event": {
                    "messageStop": {
                        "stopReason": "end_turn"
                    }
                }
            }
            
            # Emit final tool results for UI display
            if emitted_tools:
                for tool_name in emitted_tools:
                    tool_display = TOOL_DESCRIPTIONS.get(tool_name, f"🔧 {tool_name}")
                    yield {
                        "tool_stream_event": {
                            "tool_use": {"name": tool_display},
                            "data": {"result": "completed", "data": f"{tool_display} completed"}
                        }
                    }
            
            logger.info(f"Workflow execution completed. Tools used: {list(emitted_tools)}")
            
        except Exception as e:
            logger.error(f"Error in workflow streaming: {e}", exc_info=True)
            
            # Send error as text
            yield {
                "event": {
                    "contentBlockDelta": {
                        "delta": {
                            "text": f"\n\nI encountered an error processing your request. Please try again or contact us at 0800 144 8848."
                        }
                    }
                }
            }
            
            yield {
                "status": "error",
                "error": str(e)
            }
    
    @staticmethod
    async def stream_with_typing_indicator(
        workflow_graph,
        initial_state: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream workflow output with typing indicators between nodes.
        
        Args:
            workflow_graph: Compiled LangGraph workflow
            initial_state: Initial state for the workflow
            
        Yields:
            Bedrock-formatted streaming events with typing indicators
        """
        try:
            logger.info("Starting LangGraph workflow with typing indicators...")
            
            sent_message_count = len([m for m in initial_state["messages"] if isinstance(m, HumanMessage)])
            previous_node = None
            
            for state in workflow_graph.stream(initial_state):
                node_name = list(state.keys())[0]
                current_state = state[node_name]
                
                # Show node transition (optional - can be removed for cleaner output)
                if previous_node and previous_node != node_name:
                    logger.info(f"Node transition: {previous_node} → {node_name}")
                
                previous_node = node_name
                
                # Stream new messages
                messages = current_state.get("messages", [])
                
                for i, message in enumerate(messages):
                    if i < sent_message_count:
                        continue
                    
                    if isinstance(message, AIMessage) and message.content:
                        # Send message start
                        yield {
                            "event": {
                                "messageStart": {
                                    "role": "assistant"
                                }
                            }
                        }
                        
                        # Send content block start
                        yield {
                            "event": {
                                "contentBlockStart": {
                                    "start": {"text": ""},
                                    "contentBlockIndex": 0
                                }
                            }
                        }
                        
                        # Stream content
                        content = message.content
                        chunk_size = 15
                        
                        for j in range(0, len(content), chunk_size):
                            chunk = content[j:j+chunk_size]
                            yield {
                                "event": {
                                    "contentBlockDelta": {
                                        "delta": {"text": chunk},
                                        "contentBlockIndex": 0
                                    }
                                }
                            }
                        
                        # Send content block stop
                        yield {
                            "event": {
                                "contentBlockStop": {
                                    "contentBlockIndex": 0
                                }
                            }
                        }
                        
                        sent_message_count += 1
            
            # Send final message stop
            yield {
                "event": {
                    "messageStop": {
                        "stopReason": "end_turn"
                    }
                }
            }
            
            logger.info("Workflow completed")
            
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield {
                "event": {
                    "contentBlockDelta": {
                        "delta": {
                            "text": "\n\nError processing request. Please contact support."
                        }
                    }
                }
            }
