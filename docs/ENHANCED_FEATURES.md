# Enhanced Features - Citizens Advice Agent

## Overview

Six powerful new features have been added to help users get the support they need:

## 1. 🚨 Urgency-Based Appointment Scheduling

### How It Works
- Agent assesses case urgency on a scale of 1-10 based on:
  - **Time sensitivity**: Days until deadline
  - **Severity factors**: Homelessness risk, eviction notice, benefit sanction, debt enforcement, court summons, bailiff visit
  - **Vulnerability factors**: Disability, children, elderly, language barriers, mental health issues

### Priority System
- **Urgent (8-10)**: Priority slots within 2 days, marked with ⭐
- **Medium (5-7)**: Slots within 5 days
- **Standard (1-4)**: Slots within 14 days

### User Experience
1. Agent detects urgent situation
2. Calculates urgency score
3. Shows available slots (prioritized)
4. User selects time and provides phone number
5. Advisor calls at scheduled time

### Tools
- `assess_case_urgency()` - Calculate urgency score
- `get_appointment_slots()` - Get prioritized slots
- `book_appointment()` - Confirm booking

---

## 2. ⏰ Deadline Tracker

### Purpose
Track important dates and send reminders for:
- Appeal deadlines
- Eviction notice periods
- Benefit review dates
- Court dates
- Debt response deadlines

### Features
- Priority levels (low, medium, high, urgent)
- Days-until countdown
- Visual alerts for approaching deadlines
- Category organization

### Tools
- `add_deadline()` - Add new deadline
- `get_upcoming_deadlines()` - View all deadlines

### Dashboard Display
- Shows all upcoming deadlines
- Color-coded by priority
- Countdown timer
- "Today" and "Overdue" alerts

---

## 3. 📄 Document Generator

### Available Templates

#### Complaint Letter
For issues with landlords, employers, companies
- Pre-formatted professional layout
- User details auto-filled
- Clear statement of issue and resolution sought

#### Appeal Letter
For benefit decisions, housing decisions
- Includes reference numbers
- Structured reasoning section
- Formal appeal language

#### Formal Grievance
For workplace issues
- HR-ready format
- Clear documentation of issue
- Request for formal meeting

### Tools
- `generate_document()` - Create document from template

### User Experience
1. User describes their situation
2. Agent suggests appropriate document type
3. Agent gathers key details
4. Document generated instantly
5. User can view and download

---

## 4. 💷 Benefits Calculator

### Calculates Entitlements For
- Universal Credit
- Housing Benefit
- Council Tax Support
- Personal Independence Payment (PIP)

### Input Factors
- Monthly income
- Monthly rent/housing costs
- Disability status
- Number of children
- Other circumstances

### Output
- Estimated monthly entitlement for each benefit
- Total monthly support
- Comparison with current benefits (if provided)

### Tools
- `calculate_benefits()` - Estimate entitlements

### Use Cases
- "Am I entitled to benefits?"
- "How much Universal Credit should I get?"
- "Am I getting the right amount?"

---

## 5. 📍 Local Services Finder

### Service Types

#### Food Banks
- Trussell Trust locations
- Community food banks
- Distance from postcode
- Contact numbers

#### Debt Advice
- StepChange Debt Charity
- National Debtline
- Free debt counseling services

#### Legal Aid
- Legal Aid Agency offices
- Pro bono legal services
- Nearest locations

#### Housing Associations
- Local housing providers
- Social housing options
- Emergency accommodation

### Tools
- `find_local_services()` - Search by postcode and service type

### Integration
- Uses user's postcode from profile
- Shows distance to each service
- Provides contact information
- Direct phone numbers

---

## 6. 📊 Dashboard

### Centralized View
All user's appointments, deadlines, and documents in one place

### Sections

#### Upcoming Appointments
- Date and time
- Category and urgency
- Bureau name
- Phone number
- Case notes

#### Important Deadlines
- Title and description
- Due date
- Days until due
- Priority level
- Category

#### Your Documents
- Document title
- Type (complaint, appeal, grievance)
- Creation date
- View/download option

### Access
- Click "Dashboard" button in header
- Modal overlay for easy access
- Real-time updates

---

## Technical Implementation

### Backend (MCP Server)
- `enhanced_tools.py` - Core logic for all features
- `server.py` - MCP tool endpoints
- DynamoDB tables for persistence

### Frontend (React)
- `AppointmentBooking.tsx` - Booking UI
- `Dashboard.tsx` - Centralized dashboard
- Amplify Data integration

### Data Models (Amplify)
- `Appointment` - Scheduled calls
- `Deadline` - Important dates
- `Document` - Generated documents
- `BenefitsCalculation` - Calculation results

### Agent Integration
- Updated prompt with tool usage guidelines
- Automatic urgency assessment
- Proactive tool suggestions
- Context-aware recommendations

---

## Usage Examples

### Example 1: Urgent Eviction Case
```
User: "I got an eviction notice, I have 14 days to leave"

Agent:
1. Assesses urgency → Score: 9/10 (eviction + deadline)
2. Provides immediate advice on tenant rights
3. Offers priority appointment slots (next 2 days)
4. Adds deadline to tracker (14 days)
5. Generates complaint letter template
6. Finds local housing associations
```

### Example 2: Benefits Query
```
User: "I'm not sure if I'm getting the right benefits"

Agent:
1. Asks about income, rent, circumstances
2. Runs benefits calculator
3. Shows estimated entitlements
4. Compares with current benefits
5. Suggests appeal if underpaid
6. Offers to generate appeal letter
```

### Example 3: Workplace Issue
```
User: "My employer isn't paying me properly"

Agent:
1. Gathers details about the issue
2. Provides employment rights guidance
3. Generates formal grievance letter
4. Adds deadline for employer response (14 days)
5. Books appointment for follow-up support
```

---

## Benefits

### For Users
- ✅ Faster access to human advisors (urgency-based)
- ✅ Never miss important deadlines
- ✅ Professional documents instantly
- ✅ Know their benefit entitlements
- ✅ Find local support services
- ✅ Track everything in one place

### For Citizens Advice
- ✅ Efficient appointment allocation
- ✅ Prioritize urgent cases
- ✅ Reduce admin burden
- ✅ Better case tracking
- ✅ Improved user outcomes
- ✅ Data-driven insights

---

## Future Enhancements

### Potential Additions
1. **SMS/Email Reminders** - Automated deadline reminders
2. **Calendar Integration** - Add appointments to Google/Outlook
3. **PDF Generation** - Download documents as PDF
4. **Case History** - Full timeline of user's journey
5. **Advisor Notes** - Post-appointment follow-up notes
6. **Outcome Tracking** - Track case resolutions
7. **Real Bureau Integration** - Connect to actual bureau calendars
8. **Official Calculator API** - Use gov.uk benefits calculator
9. **Service Directory API** - Real-time service availability
10. **Multi-language Support** - Documents in multiple languages

---

## Deployment

All features are ready to deploy:

```bash
# Deploy updated Amplify schema
npm run deploy:amplify

# Deploy updated MCP server
npm run deploy:mcp

# Deploy updated agent
npm run deploy:agent

# Deploy frontend
npm run deploy:frontend
```

---

## Testing

### Test Scenarios

1. **High Urgency Case**
   - Mention eviction with 3-day deadline
   - Verify urgency score ≥ 8
   - Check priority slots offered

2. **Benefits Calculation**
   - Provide income and circumstances
   - Verify calculation results
   - Check saved to database

3. **Document Generation**
   - Request complaint letter
   - Verify template populated
   - Check saved to documents

4. **Dashboard**
   - Book appointment
   - Add deadline
   - Generate document
   - Verify all appear in dashboard

---

## Support

For questions or issues with these features, contact the development team or refer to the main README.md.
