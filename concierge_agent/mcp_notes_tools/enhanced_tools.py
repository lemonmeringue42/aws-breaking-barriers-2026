"""
Enhanced tools for Citizens Advice Agent
Includes: appointments, deadlines, documents, benefits calculator, local services
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class EnhancedToolsManager:
    """Manager for enhanced Citizens Advice tools"""

    def __init__(self, region_name: str = None):
        self.region = region_name or os.environ.get("AWS_REGION")
        self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
        
        # Table names from environment
        self.appointments_table_name = os.environ.get("APPOINTMENTS_TABLE_NAME")
        self.deadlines_table_name = os.environ.get("DEADLINES_TABLE_NAME")
        self.documents_table_name = os.environ.get("DOCUMENTS_TABLE_NAME")
        self.benefits_table_name = os.environ.get("BENEFITS_TABLE_NAME")
        
        # Initialize tables
        if self.appointments_table_name:
            self.appointments_table = self.dynamodb.Table(self.appointments_table_name)
        if self.deadlines_table_name:
            self.deadlines_table = self.dynamodb.Table(self.deadlines_table_name)
        if self.documents_table_name:
            self.documents_table = self.dynamodb.Table(self.documents_table_name)
        if self.benefits_table_name:
            self.benefits_table = self.dynamodb.Table(self.benefits_table_name)

    # ===== URGENCY ASSESSMENT =====
    
    def assess_urgency(self, case_details: Dict) -> int:
        """
        Assess case urgency on scale of 1-10
        
        Args:
            case_details: Dict with keys:
                - category: str (benefits, housing, employment, debt, etc.)
                - deadline_days: int (days until deadline, if any)
                - severity_factors: List[str] (homelessness_risk, benefit_sanction, etc.)
                - vulnerability_factors: List[str] (disability, children, language_barrier, etc.)
        
        Returns:
            Urgency score 1-10 (10 = most urgent)
        """
        score = 5  # Base score
        
        category = case_details.get("category", "")
        deadline_days = case_details.get("deadline_days")
        severity = case_details.get("severity_factors", [])
        vulnerability = case_details.get("vulnerability_factors", [])
        
        # Deadline urgency
        if deadline_days is not None:
            if deadline_days <= 2:
                score += 3
            elif deadline_days <= 7:
                score += 2
            elif deadline_days <= 14:
                score += 1
        
        # Severity factors
        high_severity = ["homelessness_risk", "eviction_notice", "benefit_sanction", 
                        "debt_enforcement", "court_summons", "bailiff_visit"]
        for factor in severity:
            if factor in high_severity:
                score += 2
                break
        
        # Vulnerability factors
        if len(vulnerability) >= 2:
            score += 1
        if "children" in vulnerability or "disability" in vulnerability:
            score += 1
        
        # Category-specific adjustments
        urgent_categories = ["housing", "debt"]
        if category in urgent_categories:
            score += 1
        
        return min(10, max(1, score))

    # ===== APPOINTMENTS =====
    
    def get_available_slots(self, bureau_id: str, urgency_score: int, 
                           days_ahead: int = 14) -> List[Dict]:
        """
        Get available appointment slots, prioritized by urgency
        
        Args:
            bureau_id: Bureau identifier
            urgency_score: 1-10 urgency score
            days_ahead: How many days ahead to check
        
        Returns:
            List of available slots with datetime and priority
        """
        # Mock implementation - in production, integrate with bureau calendar system
        slots = []
        now = datetime.now()
        
        # High urgency (8-10): offer slots within 2 days
        # Medium urgency (5-7): offer slots within 5 days
        # Low urgency (1-4): offer slots within 14 days
        
        if urgency_score >= 8:
            max_days = 2
        elif urgency_score >= 5:
            max_days = 5
        else:
            max_days = days_ahead
        
        # Generate slots (9am-5pm, every 30 mins, weekdays only)
        for day in range(1, max_days + 1):
            slot_date = now + timedelta(days=day)
            if slot_date.weekday() < 5:  # Monday-Friday
                for hour in range(9, 17):
                    for minute in [0, 30]:
                        slot_time = slot_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        slots.append({
                            "datetime": slot_time.isoformat(),
                            "bureau_id": bureau_id,
                            "available": True,
                            "priority_slot": urgency_score >= 8 and day <= 1
                        })
        
        return slots[:20]  # Return first 20 slots
    
    def book_appointment(self, user_id: str, appointment_details: Dict) -> Dict:
        """
        Book an appointment
        
        Args:
            user_id: User ID
            appointment_details: Dict with scheduled_time, category, urgency_score, etc.
        
        Returns:
            Appointment confirmation
        """
        import uuid
        
        appointment = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "bureauId": appointment_details.get("bureau_id", "default"),
            "bureauName": appointment_details.get("bureau_name", "Citizens Advice"),
            "scheduledTime": appointment_details["scheduled_time"],
            "duration": appointment_details.get("duration", 30),
            "urgencyScore": appointment_details["urgency_score"],
            "category": appointment_details["category"],
            "caseNotes": appointment_details.get("case_notes", ""),
            "phoneNumber": appointment_details.get("phone_number", ""),
            "status": "scheduled",
            "createdAt": datetime.now().isoformat()
        }
        
        try:
            self.appointments_table.put_item(Item=appointment)
            logger.info(f"Booked appointment for user {user_id}")
            return {
                "success": True,
                "appointment_id": appointment["id"],
                "scheduled_time": appointment["scheduledTime"],
                "message": f"Appointment booked for {appointment['scheduledTime']}"
            }
        except ClientError as e:
            logger.error(f"Error booking appointment: {e}")
            return {"success": False, "error": str(e)}

    # ===== DEADLINES =====
    
    def add_deadline(self, user_id: str, deadline_details: Dict) -> Dict:
        """Add a deadline to track"""
        import uuid
        
        deadline = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "title": deadline_details["title"],
            "description": deadline_details.get("description", ""),
            "dueDate": deadline_details["due_date"],
            "category": deadline_details["category"],
            "priority": deadline_details.get("priority", "medium"),
            "completed": False,
            "reminderSent": False,
            "createdAt": datetime.now().isoformat()
        }
        
        try:
            self.deadlines_table.put_item(Item=deadline)
            return {"success": True, "deadline_id": deadline["id"]}
        except ClientError as e:
            return {"success": False, "error": str(e)}
    
    def get_upcoming_deadlines(self, user_id: str, days_ahead: int = 30) -> List[Dict]:
        """Get upcoming deadlines"""
        try:
            response = self.deadlines_table.query(
                IndexName="userId-index",
                KeyConditionExpression="userId = :uid",
                FilterExpression="completed = :false",
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":false": False
                }
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Error getting deadlines: {e}")
            return []

    # ===== DOCUMENTS =====
    
    def generate_document(self, user_id: str, doc_details: Dict) -> Dict:
        """Generate a document (letter, form, etc.)"""
        import uuid
        
        # Document templates
        templates = {
            "complaint_letter": self._generate_complaint_letter,
            "appeal_letter": self._generate_appeal_letter,
            "formal_grievance": self._generate_formal_grievance,
        }
        
        doc_type = doc_details["type"]
        if doc_type not in templates:
            return {"success": False, "error": "Unknown document type"}
        
        content = templates[doc_type](doc_details)
        
        document = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "title": doc_details["title"],
            "type": doc_type,
            "content": content,
            "category": doc_details.get("category", ""),
            "createdAt": datetime.now().isoformat()
        }
        
        try:
            self.documents_table.put_item(Item=document)
            return {
                "success": True,
                "document_id": document["id"],
                "content": content
            }
        except ClientError as e:
            return {"success": False, "error": str(e)}
    
    def _generate_complaint_letter(self, details: Dict) -> str:
        """Generate complaint letter template"""
        return f"""
[Your Name]
[Your Address]
[Your Postcode]

{details.get('recipient_name', '[Recipient Name]')}
{details.get('recipient_address', '[Recipient Address]')}

Date: {datetime.now().strftime('%d %B %Y')}

Dear {details.get('recipient_name', 'Sir/Madam')},

Re: Formal Complaint - {details.get('subject', '[Subject]')}

I am writing to formally complain about {details.get('issue', '[describe issue]')}.

{details.get('details', '[Provide full details of the complaint]')}

I expect {details.get('resolution', '[state what you want to happen]')}.

I look forward to your response within 14 days.

Yours faithfully,
[Your Name]
"""

    def _generate_appeal_letter(self, details: Dict) -> str:
        """Generate appeal letter template"""
        return f"""
[Your Name]
[Your Address]
[National Insurance Number: {details.get('ni_number', 'XX XX XX XX X')}]

{details.get('department', '[Department]')}
{details.get('department_address', '[Address]')}

Date: {datetime.now().strftime('%d %B %Y')}

Dear Sir/Madam,

Re: Appeal Against Decision - Reference: {details.get('reference', '[REF]')}

I am writing to appeal against your decision dated {details.get('decision_date', '[date]')} regarding {details.get('subject', '[subject]')}.

I believe this decision is incorrect because:

{details.get('reasons', '[List your reasons for appeal]')}

I request that you reconsider this decision.

Yours faithfully,
[Your Name]
"""

    def _generate_formal_grievance(self, details: Dict) -> str:
        """Generate formal grievance template"""
        return f"""
FORMAL GRIEVANCE

From: [Your Name]
To: {details.get('recipient', '[Manager/HR]')}
Date: {datetime.now().strftime('%d %B %Y')}

Subject: Formal Grievance - {details.get('subject', '[Subject]')}

I wish to raise a formal grievance regarding {details.get('issue', '[issue]')}.

Details of Grievance:
{details.get('details', '[Provide full details]')}

Resolution Sought:
{details.get('resolution', '[What you want to happen]')}

I request a formal meeting to discuss this matter.

Signed: [Your Name]
Date: {datetime.now().strftime('%d %B %Y')}
"""

    # ===== BENEFITS CALCULATOR =====
    
    def calculate_benefits(self, user_id: str, circumstances: Dict) -> Dict:
        """
        Calculate potential benefit entitlements
        
        Args:
            circumstances: Dict with income, expenses, household details
        
        Returns:
            Estimated entitlements
        """
        import uuid
        
        # Simplified calculation - in production, use official calculator API
        results = {
            "universal_credit": 0,
            "housing_benefit": 0,
            "council_tax_support": 0,
            "pip": 0,
            "total_monthly": 0
        }
        
        income = circumstances.get("monthly_income", 0)
        rent = circumstances.get("monthly_rent", 0)
        has_disability = circumstances.get("has_disability", False)
        has_children = circumstances.get("has_children", False)
        num_children = circumstances.get("num_children", 0)
        
        # Universal Credit (simplified)
        if income < 1500:
            uc_standard = 368.74  # Single person standard allowance
            if has_children:
                uc_standard += 290 * num_children  # Child element
            results["universal_credit"] = max(0, uc_standard - (income * 0.55))
        
        # Housing support
        if rent > 0:
            results["housing_benefit"] = min(rent, 1200)  # Simplified cap
        
        # Council tax support
        if income < 2000:
            results["council_tax_support"] = 150  # Approximate
        
        # PIP
        if has_disability:
            results["pip"] = 434  # Standard rate daily living
        
        results["total_monthly"] = sum(results.values())
        
        # Save calculation
        calculation = {
            "id": str(uuid.uuid4()),
            "userId": user_id,
            "income": json.dumps({"monthly_income": income}),
            "expenses": json.dumps({"monthly_rent": rent}),
            "circumstances": json.dumps(circumstances),
            "results": json.dumps(results),
            "createdAt": datetime.now().isoformat()
        }
        
        try:
            self.benefits_table.put_item(Item=calculation)
        except ClientError as e:
            logger.error(f"Error saving calculation: {e}")
        
        return results

    # ===== LOCAL SERVICES =====
    
    def find_local_services(self, postcode: str, service_type: str) -> List[Dict]:
        """
        Find local services near postcode
        
        Args:
            postcode: UK postcode
            service_type: food_bank, debt_advice, legal_aid, housing_association
        
        Returns:
            List of nearby services
        """
        # Mock data - in production, integrate with real service directories
        services = {
            "food_bank": [
                {"name": "Trussell Trust Food Bank", "distance": "0.5 miles", "phone": "0808 208 2138"},
                {"name": "Community Food Bank", "distance": "1.2 miles", "phone": "0800 123 4567"},
            ],
            "debt_advice": [
                {"name": "StepChange Debt Charity", "distance": "N/A", "phone": "0800 138 1111"},
                {"name": "National Debtline", "distance": "N/A", "phone": "0808 808 4000"},
            ],
            "legal_aid": [
                {"name": "Legal Aid Agency", "distance": "2.1 miles", "phone": "0345 345 4345"},
            ],
            "housing_association": [
                {"name": "Local Housing Association", "distance": "1.5 miles", "phone": "0300 123 4567"},
            ]
        }
        
        return services.get(service_type, [])
