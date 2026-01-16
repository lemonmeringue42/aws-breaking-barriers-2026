# Citizens Advice Agent - Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                      USERS                                               │
│                                        │                                                 │
│                                        ▼                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         AMPLIFY HOSTING                                           │   │
│  │                    main.ddncho72fakwd.amplifyapp.com                              │   │
│  │  ┌────────────────────────────────────────────────────────────────────────────┐  │   │
│  │  │                         React Web UI (Vite)                                 │  │   │
│  │  │  • Chat Interface    • Benefits Calculator    • Document Generator          │  │   │
│  │  │  • Voice Mode        • Cost Monitor           • Session History             │  │   │
│  │  └────────────────────────────────────────────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────────────────┘   │
│                                        │                                                 │
└────────────────────────────────────────┼─────────────────────────────────────────────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
                    ▼                    ▼                    ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│   AMAZON COGNITO      │  │   AGENTCORE RUNTIME   │  │   API GATEWAY         │
│   (Authentication)    │  │   (Supervisor Agent)  │  │   (REST & WebSocket)  │
│                       │  │                       │  │                       │
│ • User Pool           │  │ • Python/Strands SDK  │  │ • Cost Monitor API    │
│ • OAuth2 Tokens       │  │ • Multi-agent System  │  │ • Voice Proxy WS      │
│ • JWT Validation      │  │ • Streaming Responses │  │ • Cognito Authorizer  │
└───────────────────────┘  └───────────┬───────────┘  └───────────────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
┌───────────────────────┐  ┌───────────────────────┐  ┌───────────────────────┐
│   AGENTCORE GATEWAY   │  │   AGENTCORE MEMORY    │  │   AMAZON BEDROCK      │
│   (MCP Tool Router)   │  │   (Long-term Memory)  │  │   (Foundation Models) │
│                       │  │                       │  │                       │
│ • OAuth2 Auth         │  │ • Semantic Facts      │  │ • Claude Sonnet 4.5   │
│ • Tool Discovery      │  │ • User Preferences    │  │ • Nova Sonic (Voice)  │
│ • Request Routing     │  │ • Session Summaries   │  │ • Streaming Inference │
└───────────┬───────────┘  └───────────────────────┘  └───────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                           MCP SERVERS (Tools)                                  │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐    │
│  │   Notes MCP Server  │  │   Triage Tool       │  │   Document Generator│    │
│  │                     │  │   (Built-in)        │  │   (Built-in)        │    │
│  │ • Create/Read Notes │  │                     │  │                     │    │
│  │ • Search Notes      │  │ • Urgency Scoring   │  │ • Letter Templates  │    │
│  │ • Case Management   │  │ • Crisis Detection  │  │ • Form Generation   │    │
│  └─────────────────────┘  │ • Queue Management  │  │ • S3 Storage        │    │
│                           └─────────────────────┘  └─────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                        │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐    │
│  │   DynamoDB Tables   │  │   S3 Buckets        │  │   SNS Topics        │    │
│  │                     │  │                     │  │                     │    │
│  │ • User              │  │ • Documents         │  │ • Crisis Alerts     │    │
│  │ • UserProfile       │  │   (Generated PDFs)  │  │   (Email Notifs)    │    │
│  │ • ChatSession       │  │                     │  │                     │    │
│  │ • ChatMessage       │  │ • Frontend Assets   │  │                     │    │
│  │ • Notes             │  │   (Deploy Bucket)   │  │                     │    │
│  │ • Appointment       │  │                     │  │                     │    │
│  │ • Deadline          │  └─────────────────────┘  └─────────────────────┘    │
│  │ • Document          │                                                       │
│  │ • Feedback          │  ┌─────────────────────┐  ┌─────────────────────┐    │
│  │ • CaseQueue         │  │   EventBridge       │  │   Lambda Functions  │    │
│  │ • LocalBureau       │  │                     │  │                     │    │
│  │ • BenefitsCalc      │  │ • Daily 9am Trigger │  │ • Notifications     │    │
│  └─────────────────────┘  │   (Notifications)   │  │ • Cost Monitor      │    │
│                           └─────────────────────┘  │ • OAuth Provider    │    │
│                                                    │ • Voice Proxy       │    │
│                                                    └─────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────────┘


                              DATA FLOW
                              ─────────

  1. User authenticates via Cognito → JWT token issued
  2. User sends message → Web UI calls AgentCore Runtime with JWT
  3. Runtime validates JWT, invokes Supervisor Agent
  4. Agent uses Bedrock (Claude) for reasoning
  5. Agent retrieves/stores context via AgentCore Memory
  6. Agent calls MCP tools via AgentCore Gateway
  7. Response streamed back to user
  8. Daily: EventBridge triggers Notifications Lambda
     → Scans Deadlines/Appointments → Sends reminder emails via SES


                           NOTIFICATION FLOW
                           ─────────────────

  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │ EventBridge │────▶│   Lambda    │────▶│  DynamoDB   │────▶│    SES      │
  │ (9am daily) │     │ Notifications│     │  (Scan)     │     │  (Email)    │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                             │
                             ▼
                      • Deadline reminders (3 days before)
                      • Appointment follow-ups (24h after)
                      • Benefit review reminders


                           CRISIS FLOW
                           ───────────

  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
  │   Agent     │────▶│ Triage Tool │────▶│    SNS      │────▶│   Email     │
  │ (Detects    │     │ (CRISIS     │     │  Topic      │     │  Alerts     │
  │  urgency)   │     │  level)     │     │             │     │             │
  └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Key Components

| Component | Service | Purpose |
|-----------|---------|---------|
| Frontend | Amplify Hosting | React chat UI with voice support |
| Auth | Cognito | User authentication, JWT tokens |
| Agent | AgentCore Runtime | AI agent execution environment |
| LLM | Bedrock (Claude) | Natural language understanding |
| Memory | AgentCore Memory | Long-term context storage |
| Tools | AgentCore Gateway + MCP | External tool integration |
| Data | DynamoDB | User data, sessions, notes |
| Notifications | EventBridge + Lambda + SES | Proactive reminders |
| Alerts | SNS | Crisis case notifications |

## Deployment Stacks

1. **Amplify Backend** (`npm run deploy:amplify`)
   - Cognito, DynamoDB tables, GraphQL API, Notifications Lambda

2. **MCP Servers** (`npm run deploy:mcp`)
   - Notes MCP Server runtime

3. **Agent Stack** (`npm run deploy:agent`)
   - AgentCore Runtime, Gateway, Memory, Cost Monitor API

4. **Frontend** (`npm run deploy:frontend`)
   - Amplify Hosting app
