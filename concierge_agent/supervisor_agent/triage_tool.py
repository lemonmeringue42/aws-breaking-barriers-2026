"""
Triage and Case Routing Tool
Classifies urgency and routes cases appropriately.
"""

import os
import logging
import boto3
from datetime import datetime, timedelta
from strands import tool
import json

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-west-2")
CASE_QUEUE_TABLE = os.getenv("CASE_QUEUE_TABLE_NAME")

dynamodb = boto3.resource("dynamodb", region_name=REGION)
sns = boto3.client("sns", region_name=REGION)

URGENCY_LEVELS = {
    "CRISIS": {
        "priority": 1,
        "callback_hours": 0,  # Immediate
        "description": "Life-threatening or immediate danger"
    },
    "URGENT": {
        "priority": 2,
        "callback_hours": 24,
        "description": "Time-sensitive, needs response within 24-48 hours"
    },
    "STANDARD": {
        "priority": 3,
        "callback_hours": 168,  # 1 week
        "description": "Important but not immediately time-sensitive"
    },
    "GENERAL": {
        "priority": 4,
        "callback_hours": None,  # No callback needed
        "description": "General information, handled by agent"
    }
}


@tool
async def classify_and_route_case(
    urgency_level: str,
    issue_category: str,
    time_sensitivity: str,
    user_id: str,
    session_id: str,
    summary: str
) -> str:
    """
    Classify case urgency and create routing ticket.
    
    Call this tool when you've gathered enough information to assess urgency.
    
    Args:
        urgency_level: Must be one of: "CRISIS", "URGENT", "STANDARD", "GENERAL"
            - CRISIS: Suicidal thoughts, domestic violence, homeless tonight, immediate danger
            - URGENT: Eviction <7 days, benefit sanction, no food/heating, vulnerable person
            - STANDARD: Eviction >7 days, employment dispute, debt issues, housing repairs
            - GENERAL: Information seeking, general advice (no callback needed)
        
        issue_category: Type of issue - "mental_health", "domestic_abuse", "eviction", 
            "benefits", "employment", "debt", "housing", "consumer", "immigration"
        
        time_sensitivity: "immediate" (today), "days" (within week), "weeks" (within month), "none"
        
        user_id: User's unique identifier (from context)
        session_id: Current session ID (from context)
        summary: Brief 1-2 sentence summary of the case
    
    Returns:
        Confirmation message with next steps
    """
    try:
        logger.info(f"🔔 TRIAGE TOOL CALLED: urgency={urgency_level}, category={issue_category}")
        
        # Validate urgency level
        if urgency_level not in URGENCY_LEVELS:
            return f"Invalid urgency level. Must be one of: {', '.join(URGENCY_LEVELS.keys())}"
        
        urgency_config = URGENCY_LEVELS[urgency_level]
        case_id = f"case-{user_id}-{int(datetime.now().timestamp())}"
        
        # Calculate callback time
        callback_time = None
        if urgency_config["callback_hours"] is not None:
            callback_time = (datetime.now() + timedelta(hours=urgency_config["callback_hours"])).isoformat()
        
        # Create case record
        case_data = {
            "caseId": case_id,
            "userId": user_id,
            "sessionId": session_id,
            "urgencyLevel": urgency_level,
            "priority": urgency_config["priority"],
            "issueCategory": issue_category,
            "timeSensitivity": time_sensitivity,
            "summary": summary,
            "status": "PENDING",
            "createdAt": datetime.now().isoformat(),
            "scheduledCallbackTime": callback_time,
            "lastUpdated": datetime.now().isoformat()
        }
        
        # Store in DynamoDB
        if CASE_QUEUE_TABLE:
            table = dynamodb.Table(CASE_QUEUE_TABLE)
            table.put_item(Item=case_data)
            logger.info(f"✅ Created case {case_id} with urgency {urgency_level}")
        else:
            logger.error("CASE_QUEUE_TABLE not set!")
            return "Error: Case queue not configured"
        
        # Handle CRISIS cases - send immediate alert
        if urgency_level == "CRISIS":
            sns_topic_arn = os.getenv("CRISIS_ALERT_TOPIC_ARN")
            if sns_topic_arn:
                try:
                    sns.publish(
                        TopicArn=sns_topic_arn,
                        Subject=f"🚨 CRISIS CASE: {issue_category}",
                        Message=json.dumps({
                            "caseId": case_id,
                            "userId": user_id,
                            "issueCategory": issue_category,
                            "summary": summary,
                            "timestamp": datetime.now().isoformat()
                        }, indent=2)
                    )
                    logger.info(f"📧 Sent crisis alert for case {case_id}")
                except Exception as e:
                    logger.error(f"Failed to send SNS alert: {e}")
            
            return f"""✅ CRISIS case logged (ID: {case_id})

Emergency services have been notified. A crisis advisor will contact you as soon as possible.

In the meantime, please use the emergency contact numbers I provided earlier if you need immediate support."""
        
        # Handle URGENT cases
        elif urgency_level == "URGENT":
            return f"""✅ Case logged as URGENT (ID: {case_id})

An advisor will call you within 24-48 hours to discuss your situation.

We've noted:
- Issue: {issue_category}
- Time sensitivity: {time_sensitivity}
- Summary: {summary}

You'll receive a confirmation email shortly. In the meantime, I can continue to provide guidance."""
        
        # Handle STANDARD cases
        elif urgency_level == "STANDARD":
            return f"""✅ Case logged (ID: {case_id})

An advisor will contact you within 1 week to provide personalized support.

Case details:
- Issue: {issue_category}
- Summary: {summary}

I can continue to help you with immediate questions while you wait for the callback."""
        
        # GENERAL - no callback needed
        else:
            return f"""✅ Information logged for reference (ID: {case_id})

I can continue to help you with your questions. No callback is scheduled as this appears to be general information seeking.

If your situation changes or becomes more urgent, please let me know."""
    
    except Exception as e:
        logger.error(f"Error in classify_and_route_case: {e}", exc_info=True)
        return f"I've noted your case but encountered an error logging it. Please contact Citizens Advice directly at 0800 144 8848 to ensure your case is recorded."
