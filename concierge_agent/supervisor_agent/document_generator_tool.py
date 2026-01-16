"""
Document Generator Tool
Generate template letters for common Citizens Advice scenarios.
"""

import os
import logging
import boto3
from datetime import datetime, timedelta
from strands import tool

logger = logging.getLogger(__name__)

REGION = os.getenv("AWS_REGION", "us-west-2")
DOCUMENTS_BUCKET = os.getenv("DOCUMENTS_BUCKET_NAME")

s3 = boto3.client("s3", region_name=REGION)

# Letter templates
TEMPLATES = {
    "benefit_appeal": """
{date}

{user_name}
{user_address}

Department for Work and Pensions
Benefit Appeals Team

Dear Sir/Madam,

RE: Appeal Against {benefit_type} Decision - Reference: {reference_number}

I am writing to formally appeal the decision made on {decision_date} regarding my {benefit_type} claim.

GROUNDS FOR APPEAL:
{appeal_grounds}

SUPPORTING INFORMATION:
{supporting_info}

I believe this decision is incorrect because:
{reasons}

I request that this decision be reconsidered. I am willing to provide any additional information or evidence required to support my appeal.

Please acknowledge receipt of this appeal and inform me of the next steps in the process.

Yours faithfully,

{user_name}
{contact_phone}
{contact_email}
""",

    "landlord_complaint": """
{date}

{user_name}
{user_address}

{landlord_name}
{landlord_address}

Dear {landlord_name},

RE: Formal Complaint - {property_address}

I am writing to formally complain about {issue_type} at the above property.

ISSUE DETAILS:
{issue_description}

DATE ISSUE FIRST REPORTED: {first_reported_date}

IMPACT ON TENANT:
{impact_description}

LEGAL OBLIGATIONS:
Under the Landlord and Tenant Act 1985, you are legally required to keep the property in good repair. This includes {specific_obligations}.

ACTION REQUIRED:
I request that you {requested_action} within 14 days of receiving this letter.

If this matter is not resolved within a reasonable timeframe, I will have no choice but to:
- Contact the local council's environmental health department
- Seek advice from Citizens Advice
- Consider legal action for breach of tenancy agreement

I look forward to your prompt response.

Yours sincerely,

{user_name}
{contact_phone}
{contact_email}
""",

    "debt_negotiation": """
{date}

{user_name}
{user_address}

{creditor_name}
{creditor_address}

Account Reference: {account_reference}

Dear Sir/Madam,

RE: Request for Payment Arrangement

I am writing regarding the above account. I am currently experiencing financial difficulties due to {reason_for_hardship}.

CURRENT FINANCIAL SITUATION:
Monthly Income: £{monthly_income}
Essential Expenses: £{monthly_expenses}
Available for Debt Repayment: £{available_amount}

I am committed to repaying this debt and would like to propose a payment arrangement of £{proposed_payment} per month.

This offer is based on my current financial circumstances and represents a fair and affordable payment plan. I have sought advice from Citizens Advice to ensure this is sustainable.

SUPPORTING EVIDENCE:
I can provide the following documentation to support this request:
{supporting_documents}

I would appreciate your consideration of this proposal. Please confirm in writing if this arrangement is acceptable.

If you require any further information, please do not hesitate to contact me.

Yours faithfully,

{user_name}
{contact_phone}
{contact_email}
""",

    "employer_grievance": """
{date}

{user_name}
{user_address}

{employer_name}
{employer_address}

Dear {manager_name},

RE: Formal Grievance - {grievance_type}

I am writing to raise a formal grievance under the company's grievance procedure.

NATURE OF GRIEVANCE:
{grievance_description}

DATE(S) OF INCIDENT(S):
{incident_dates}

PARTIES INVOLVED:
{parties_involved}

IMPACT:
This situation has caused me {impact_description}.

RESOLUTION SOUGHT:
I would like to see the following resolution:
{desired_resolution}

I have attempted to resolve this matter informally by {informal_attempts}, but the issue remains unresolved.

I request a formal grievance meeting to discuss this matter further. I would like to be accompanied by {companion_details} as is my right under employment law.

Please acknowledge receipt of this grievance within 5 working days and arrange a meeting within a reasonable timeframe.

Yours sincerely,

{user_name}
{contact_phone}
{contact_email}
""",

    "consumer_complaint": """
{date}

{user_name}
{user_address}

{company_name}
{company_address}

Order/Reference Number: {order_reference}

Dear Sir/Madam,

RE: Complaint Regarding {product_or_service}

I am writing to complain about {product_or_service} purchased from your company on {purchase_date}.

ISSUE:
{issue_description}

CONSUMER RIGHTS:
Under the Consumer Rights Act 2015, goods must be:
- Of satisfactory quality
- Fit for purpose
- As described

The {product_or_service} I received does not meet these requirements because {specific_failure}.

RESOLUTION REQUESTED:
I am requesting {requested_remedy} within 14 days of receiving this letter.

EVIDENCE:
I have attached/enclosed:
{evidence_list}

If this matter is not resolved satisfactorily, I will consider:
- Reporting to Trading Standards
- Pursuing a claim through the small claims court
- Leaving reviews on consumer platforms

I look forward to your prompt response.

Yours faithfully,

{user_name}
{contact_phone}
{contact_email}
""",

    "mp_letter": """
{date}

{user_name}
{user_address}

{mp_name}
House of Commons
London
SW1A 0AA

Dear {mp_name},

RE: {subject}

I am writing to you as my Member of Parliament to raise concerns about {issue_category} in our constituency.

THE ISSUE:
{issue_description}

HOW THIS AFFECTS ME/OUR COMMUNITY:
{impact_description}

WHAT I AM ASKING YOU TO DO:
{requested_action}

BACKGROUND:
{background_info}

I would be grateful if you could:
1. Look into this matter
2. Raise it with the relevant minister or department if appropriate
3. Let me know what action you are able to take

I am happy to provide any additional information or meet with you to discuss this further.

Thank you for your time and attention to this matter. I look forward to hearing from you.

Yours sincerely,

{user_name}
{contact_phone}
{contact_email}
"""
}


@tool
def generate_letter(
    letter_type: str,
    user_name: str = "Not provided",
    user_address: str = "Not provided",
    contact_phone: str = "Not provided",
    contact_email: str = "Not provided",
    **kwargs
) -> str:
    """
    Generate a formal letter for common Citizens Advice scenarios.
    
    CALL THIS TOOL when user asks to create/write/draft a letter. Use information from the conversation.
    
    Args:
        letter_type: Type of letter. MUST be one of:
            - "employer_grievance": Workplace issues (unpaid wages, discrimination, grievances)
            - "benefit_appeal": Appeal DWP/benefits decisions
            - "landlord_complaint": Housing repairs, landlord issues
            - "debt_negotiation": Payment plans with creditors
            - "consumer_complaint": Faulty goods/services
            - "mp_letter": Letter to Member of Parliament about local/national issues
        
        user_name: User's full name (use from profile if available)
        user_address: User's address (use from profile if available)
        contact_phone: Phone number (optional)
        contact_email: Email address (use from profile if available)
        
        **kwargs: Additional fields - use [Not provided] for any missing info:
        
        For employer_grievance (unpaid wages, workplace issues):
            - employer_name: Company name
            - employer_address: Company address (use "Address to be added" if unknown)
            - manager_name: Manager or HR name (use "HR Department" if unknown)
            - grievance_type: e.g., "Unpaid Wages"
            - grievance_description: What happened
            - incident_dates: When it happened
            - parties_involved: Who is involved
            - impact_description: How it affects the user
            - desired_resolution: What they want (e.g., "Payment of £1,300 owed")
            - informal_attempts: Previous attempts to resolve
            - companion_details: "a colleague or trade union representative"
    
    Returns:
        The generated letter or download link
    """
    try:
        logger.info(f"📝 Generating {letter_type} letter for {user_name}")
        
        if letter_type not in TEMPLATES:
            return f"Unknown letter type: {letter_type}. Available types: {', '.join(TEMPLATES.keys())}"
        
        # Get template
        template = TEMPLATES[letter_type]
        
        # Prepare variables with defaults for missing fields
        default_values = {
            "date": datetime.now().strftime("%d %B %Y"),
            "user_name": user_name,
            "user_address": user_address,
            "contact_phone": contact_phone,
            "contact_email": contact_email,
            # Employer grievance defaults
            "employer_name": "[Employer Name]",
            "employer_address": "[Employer Address]",
            "manager_name": "HR Department",
            "grievance_type": "[Grievance Type]",
            "grievance_description": "[Description to be added]",
            "incident_dates": "[Dates to be added]",
            "parties_involved": "[Parties involved]",
            "impact_description": "[Impact description]",
            "desired_resolution": "[Desired resolution]",
            "informal_attempts": "[Previous attempts]",
            "companion_details": "a colleague or trade union representative",
            # Other template defaults
            "benefit_type": "[Benefit Type]",
            "reference_number": "[Reference Number]",
            "decision_date": "[Decision Date]",
            "appeal_grounds": "[Appeal Grounds]",
            "supporting_info": "[Supporting Information]",
            "reasons": "[Reasons]",
            "landlord_name": "[Landlord Name]",
            "landlord_address": "[Landlord Address]",
            "property_address": "[Property Address]",
            "issue_type": "[Issue Type]",
            "issue_description": "[Issue Description]",
            "first_reported_date": "[Date First Reported]",
            "specific_obligations": "[Specific Obligations]",
            "requested_action": "[Requested Action]",
            "creditor_name": "[Creditor Name]",
            "creditor_address": "[Creditor Address]",
            "account_reference": "[Account Reference]",
            "reason_for_hardship": "[Reason for Hardship]",
            "monthly_income": "[Amount]",
            "monthly_expenses": "[Amount]",
            "available_amount": "[Amount]",
            "proposed_payment": "[Amount]",
            "supporting_documents": "[List of Documents]",
            "company_name": "[Company Name]",
            "company_address": "[Company Address]",
            "order_reference": "[Order Reference]",
            "product_or_service": "[Product/Service]",
            "purchase_date": "[Purchase Date]",
            "specific_failure": "[Specific Failure]",
            "requested_remedy": "[Requested Remedy]",
            "evidence_list": "[Evidence List]",
            # MP letter defaults
            "mp_name": "[Your MP's Name]",
            "subject": "[Subject of Your Concern]",
            "issue_category": "[Issue Category]",
            "impact_description": "[How This Affects You/Community]",
            "requested_action": "[What You Want Your MP To Do]",
            "background_info": "[Any Background Information]",
        }
        
        # Merge defaults with provided kwargs
        variables = {**default_values, **kwargs}
        
        # Fill template
        try:
            letter_content = template.format(**variables)
        except KeyError as e:
            missing_field = str(e).strip("'")
            return f"Missing required field for {letter_type} letter: {missing_field}. Please provide this information."
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"letters/{letter_type}_{user_name.replace(' ', '_')}_{timestamp}.txt"
        
        # Upload to S3
        if DOCUMENTS_BUCKET:
            try:
                s3.put_object(
                    Bucket=DOCUMENTS_BUCKET,
                    Key=filename,
                    Body=letter_content.encode('utf-8'),
                    ContentType='text/plain'
                )
                
                # Generate pre-signed URL (valid for 7 days)
                download_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': DOCUMENTS_BUCKET, 'Key': filename},
                    ExpiresIn=604800  # 7 days
                )
                
                logger.info(f"✅ Letter generated and uploaded: {filename}")
                
                return f"""✅ **Letter Generated Successfully**

Your {letter_type.replace('_', ' ').title()} letter has been created.

📥 **Download your letter:**
{download_url}

⏰ **This link expires in 7 days**

📋 **Next Steps:**
1. Download and review the letter
2. Make any personal adjustments if needed
3. Print and sign the letter
4. Keep a copy for your records
5. Send via recorded delivery for proof of postage

💡 **Tip:** Always keep copies of all correspondence for your records.

<LETTER_PREVIEW>
{letter_content}
</LETTER_PREVIEW>"""
            
            except Exception as e:
                logger.error(f"Failed to upload to S3: {e}")
                # Fallback: return the letter content directly
                return f"""✅ **Letter Generated**

<LETTER_PREVIEW>
{letter_content}
</LETTER_PREVIEW>

💡 **Tip:** Review carefully and make any necessary adjustments before sending."""
        
        else:
            # No S3 bucket configured, return content directly
            return f"""✅ **Letter Generated**

<LETTER_PREVIEW>
{letter_content}
</LETTER_PREVIEW>

---

💡 **Tip:** Copy this letter, review it carefully, and make any necessary adjustments before sending."""
    
    except Exception as e:
        logger.error(f"Error generating letter: {e}", exc_info=True)
        return "I encountered an error generating the letter. Please try again or contact us for assistance."
