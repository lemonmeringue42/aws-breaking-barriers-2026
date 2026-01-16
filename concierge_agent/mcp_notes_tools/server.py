from mcp.server.fastmcp import FastMCP
from dynamodb_manager import NotesManager
from enhanced_tools import EnhancedToolsManager
import json

mcp = FastMCP(host="0.0.0.0", stateless_http=True)
notes_manager = NotesManager()
tools_manager = EnhancedToolsManager()

# ===== NOTES =====

@mcp.tool()
def add_note(user_id: str, content: str, category: str = "general") -> str:
    """Save a note for the user. Categories: benefits, housing, employment, consumer, debt, other"""
    result = notes_manager.add_note(user_id, content, category)
    return f"Note saved: {result['noteId']}"

@mcp.tool()
def get_notes(user_id: str, category: str = None) -> str:
    """Get all notes for a user, optionally filtered by category"""
    notes = notes_manager.get_notes(user_id, category)
    return str(notes)

@mcp.tool()
def delete_note(user_id: str, note_id: str) -> str:
    """Delete a specific note"""
    notes_manager.delete_note(user_id, note_id)
    return "Note deleted"

# ===== URGENCY & APPOINTMENTS =====

@mcp.tool()
def assess_case_urgency(
    category: str,
    deadline_days: int = None,
    severity_factors: str = "",
    vulnerability_factors: str = ""
) -> str:
    """
    Assess urgency of a case on scale 1-10.
    
    Args:
        category: benefits, housing, employment, consumer, debt, immigration
        deadline_days: Days until deadline (if any)
        severity_factors: Comma-separated (homelessness_risk, eviction_notice, benefit_sanction, debt_enforcement, court_summons, bailiff_visit)
        vulnerability_factors: Comma-separated (disability, children, elderly, language_barrier, mental_health)
    
    Returns urgency score and explanation
    """
    case_details = {
        "category": category,
        "deadline_days": deadline_days,
        "severity_factors": severity_factors.split(",") if severity_factors else [],
        "vulnerability_factors": vulnerability_factors.split(",") if vulnerability_factors else []
    }
    
    score = tools_manager.assess_urgency(case_details)
    
    explanation = f"Urgency score: {score}/10"
    if score >= 8:
        explanation += " (URGENT - priority appointment needed)"
    elif score >= 5:
        explanation += " (Medium urgency - appointment within 5 days)"
    else:
        explanation += " (Standard - appointment within 2 weeks)"
    
    return explanation

@mcp.tool()
def get_appointment_slots(bureau_id: str, urgency_score: int) -> str:
    """
    Get available appointment slots prioritized by urgency.
    Higher urgency = earlier slots offered.
    
    Args:
        bureau_id: Bureau identifier (use 'default' if unknown)
        urgency_score: 1-10 urgency score from assess_case_urgency
    
    Returns available slots
    """
    slots = tools_manager.get_available_slots(bureau_id, urgency_score)
    return json.dumps(slots, indent=2)

@mcp.tool()
def book_appointment(
    user_id: str,
    scheduled_time: str,
    category: str,
    urgency_score: int,
    case_notes: str = "",
    phone_number: str = "",
    bureau_id: str = "default"
) -> str:
    """
    Book an appointment with an advisor.
    
    Args:
        user_id: User ID
        scheduled_time: ISO datetime string
        category: benefits, housing, employment, etc.
        urgency_score: 1-10 urgency score
        case_notes: Brief summary of the case
        phone_number: Contact number for the call
        bureau_id: Bureau identifier
    
    Returns confirmation
    """
    details = {
        "scheduled_time": scheduled_time,
        "category": category,
        "urgency_score": urgency_score,
        "case_notes": case_notes,
        "phone_number": phone_number,
        "bureau_id": bureau_id
    }
    
    result = tools_manager.book_appointment(user_id, details)
    return json.dumps(result)

# ===== DEADLINES =====

@mcp.tool()
def add_deadline(
    user_id: str,
    title: str,
    due_date: str,
    category: str,
    description: str = "",
    priority: str = "medium"
) -> str:
    """
    Add a deadline to track.
    
    Args:
        user_id: User ID
        title: Deadline title (e.g., "Appeal deadline")
        due_date: ISO date string
        category: benefits, housing, employment, etc.
        description: Additional details
        priority: low, medium, high, urgent
    
    Returns confirmation
    """
    details = {
        "title": title,
        "due_date": due_date,
        "category": category,
        "description": description,
        "priority": priority
    }
    
    result = tools_manager.add_deadline(user_id, details)
    return json.dumps(result)

@mcp.tool()
def get_upcoming_deadlines(user_id: str) -> str:
    """Get all upcoming deadlines for a user"""
    deadlines = tools_manager.get_upcoming_deadlines(user_id)
    return json.dumps(deadlines, indent=2)

# ===== DOCUMENTS =====

@mcp.tool()
def generate_document(
    user_id: str,
    doc_type: str,
    title: str,
    recipient_name: str = "",
    subject: str = "",
    issue: str = "",
    details: str = "",
    resolution: str = ""
) -> str:
    """
    Generate a document (letter, form, etc.).
    
    Args:
        user_id: User ID
        doc_type: complaint_letter, appeal_letter, formal_grievance
        title: Document title
        recipient_name: Who the letter is addressed to
        subject: Subject of the letter
        issue: Description of the issue
        details: Full details
        resolution: What you want to happen
    
    Returns generated document
    """
    doc_details = {
        "type": doc_type,
        "title": title,
        "recipient_name": recipient_name,
        "subject": subject,
        "issue": issue,
        "details": details,
        "resolution": resolution
    }
    
    result = tools_manager.generate_document(user_id, doc_details)
    return json.dumps(result)

# ===== BENEFITS CALCULATOR =====

@mcp.tool()
def calculate_benefits(
    user_id: str,
    monthly_income: float,
    monthly_rent: float = 0,
    has_disability: bool = False,
    has_children: bool = False,
    num_children: int = 0
) -> str:
    """
    Calculate potential benefit entitlements.
    
    Args:
        user_id: User ID
        monthly_income: Monthly income in GBP
        monthly_rent: Monthly rent in GBP
        has_disability: Whether user has a disability
        has_children: Whether user has children
        num_children: Number of children
    
    Returns estimated entitlements
    """
    circumstances = {
        "monthly_income": monthly_income,
        "monthly_rent": monthly_rent,
        "has_disability": has_disability,
        "has_children": has_children,
        "num_children": num_children
    }
    
    results = tools_manager.calculate_benefits(user_id, circumstances)
    return json.dumps(results, indent=2)

# ===== LOCAL SERVICES =====

@mcp.tool()
def find_local_services(postcode: str, service_type: str) -> str:
    """
    Find local services near a postcode.
    
    Args:
        postcode: UK postcode
        service_type: food_bank, debt_advice, legal_aid, housing_association
    
    Returns list of nearby services
    """
    services = tools_manager.find_local_services(postcode, service_type)
    return json.dumps(services, indent=2)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
