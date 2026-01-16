"""
Appointment Booking Tool
Book callback appointments with Citizens Advice advisors.
"""

import os
import logging
import boto3
from datetime import datetime, timedelta
from strands import tool
import uuid

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-west-2")
BOOKINGS_TABLE = os.getenv("BOOKINGS_TABLE_NAME")

dynamodb = boto3.resource("dynamodb", region_name=REGION)


def get_available_slots(days_ahead: int = 5) -> list:
    """Generate available slots for the next N days (9am-5pm, 30min slots)."""
    slots = []
    now = datetime.now()
    
    for day_offset in range(1, days_ahead + 1):
        date = now + timedelta(days=day_offset)
        # Skip weekends
        if date.weekday() >= 5:
            continue
        
        for hour in range(9, 17):  # 9am to 5pm
            for minute in [0, 30]:
                slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                slots.append({
                    "slot_id": f"{slot_time.strftime('%Y%m%d_%H%M')}",
                    "datetime": slot_time.isoformat(),
                    "display": slot_time.strftime("%A %d %B at %H:%M"),
                    "date": slot_time.strftime("%Y-%m-%d"),
                    "time": slot_time.strftime("%H:%M")
                })
    
    return slots


def check_slot_available(slot_id: str) -> bool:
    """Check if a slot is still available."""
    if not BOOKINGS_TABLE:
        return True
    
    try:
        table = dynamodb.Table(BOOKINGS_TABLE)
        response = table.query(
            IndexName="SlotIndex",
            KeyConditionExpression="slotId = :sid",
            ExpressionAttributeValues={":sid": slot_id},
            Limit=1
        )
        return response.get("Count", 0) == 0
    except Exception as e:
        logger.error(f"Error checking slot: {e}")
        return True


@tool
def get_booking_slots(urgency_level: str = "STANDARD") -> str:
    """
    Get available appointment slots for booking a callback.
    
    Call this when user wants to book an appointment or schedule a callback.
    
    Args:
        urgency_level: URGENT (shows next 2 days) or STANDARD (shows next 5 days)
    
    Returns:
        JSON list of available slots for the UI to display
    """
    try:
        days = 2 if urgency_level == "URGENT" else 5
        slots = get_available_slots(days)
        
        # Filter out booked slots
        available = [s for s in slots if check_slot_available(s["slot_id"])]
        
        if not available:
            return "No available slots found. Please call us directly at 0800 144 8848."
        
        # Return structured data for UI
        import json
        return json.dumps({
            "type": "booking_slots",
            "urgency": urgency_level,
            "slots": available[:10],  # Limit to 10 options
            "message": "Please select a convenient time for your callback:"
        })
    
    except Exception as e:
        logger.error(f"Error getting slots: {e}")
        return "Unable to retrieve available slots. Please call 0800 144 8848."


@tool
def book_appointment(
    slot_id: str,
    user_id: str,
    user_name: str,
    contact_phone: str,
    issue_category: str,
    urgency_level: str,
    case_summary: str,
    contact_email: str = ""
) -> str:
    """
    Book a callback appointment with an advisor.
    
    Call this after user selects a time slot from get_booking_slots.
    
    Args:
        slot_id: The slot ID from get_booking_slots (format: YYYYMMDD_HHMM)
        user_id: User's unique identifier
        user_name: User's name for the advisor
        contact_phone: Phone number to call back on
        issue_category: Type of issue (benefits, housing, employment, etc.)
        urgency_level: URGENT or STANDARD
        case_summary: Brief summary of the issue
        contact_email: Optional email for confirmation
    
    Returns:
        Booking confirmation with reference number
    """
    try:
        # Parse slot datetime
        slot_date = datetime.strptime(slot_id, "%Y%m%d_%H%M")
        
        # Check availability
        if not check_slot_available(slot_id):
            return "Sorry, this slot has just been booked. Please select another time."
        
        # Create booking
        booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
        
        booking = {
            "bookingId": booking_id,
            "slotId": slot_id,
            "userId": user_id,
            "userName": user_name,
            "contactPhone": contact_phone,
            "contactEmail": contact_email,
            "issueCategory": issue_category,
            "urgencyLevel": urgency_level,
            "caseSummary": case_summary,
            "appointmentTime": slot_date.isoformat(),
            "status": "CONFIRMED",
            "createdAt": datetime.now().isoformat()
        }
        
        # Save to DynamoDB
        if BOOKINGS_TABLE:
            table = dynamodb.Table(BOOKINGS_TABLE)
            table.put_item(Item=booking)
            logger.info(f"✅ Booking created: {booking_id}")
        
        display_time = slot_date.strftime("%A %d %B at %H:%M")
        
        return f"""✅ **Appointment Confirmed**

📅 **Reference:** {booking_id}
🕐 **Time:** {display_time}
📞 **We'll call:** {contact_phone}

**What happens next:**
1. An advisor will call you at the scheduled time
2. Have any relevant documents ready
3. The call will last approximately 30 minutes

**Need to cancel or reschedule?**
Quote your reference number: {booking_id}

We look forward to speaking with you."""

    except Exception as e:
        logger.error(f"Error booking appointment: {e}")
        return "Unable to complete booking. Please call 0800 144 8848 to book directly."
