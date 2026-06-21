# Architecture Overview

This document explains the system design of the Customer Support AI Chatbot — how all the components fit together, why each exists, and how data flows through the system.

---

## High-Level Overview

The chatbot is an AI-powered support platform that receives customer messages, understands them, retrieves relevant company knowledge, calls business tools, generates grounded responses, and escalates to humans when needed.

```
Customer
   ↓
Chat Interface (Web / Mobile / Widget)
   ↓
API Gateway  ←→  Auth / Session Service
   ↓
Chat Orchestrator (FastAPI)
   ↓
┌──────────────────────────────────────────────┐
│              Processing Pipeline              │
│                                              │
│  PII Redaction → NLU → Agent Router          │
│                           ↓                  │
│              ┌────────────┴───────────┐      │
│              ↓                        ↓      │
│         RAG Service              MCP Tools   │
│         (retrieval)              (actions)   │
│              ↓                        ↓      │
│              └────────────┬───────────┘      │
│                           ↓                  │
│                      LLM Service             │
│                           ↓                  │
│                   Output Guardrails          │
└──────────────────────────────────────────────┘
   ↓
Response back to Customer
   ↓
Logs → Observability Platform
```

---

## Component Breakdown

### 1. Chat Interface

The entry point for the customer. This can be:
- A web chat widget embedded in a product
- A mobile app
- An internal support console

The interface collects the customer's message and sends it to the API Gateway over HTTPS.

---

### 2. API Gateway

Acts as the front door for all incoming requests.

**Responsibilities:**
- Route requests to the correct service
- Validate authentication tokens (JWT / OAuth)
- Apply rate limiting to prevent abuse
- Log all incoming requests for audit purposes

**Why it exists:**
Without a gateway, every service would need to handle auth and rate limiting individually. The gateway centralises these concerns.

---

### 3. Auth / Session Service

Manages who the customer is and what they are allowed to do.

**Responsibilities:**
- Verify the customer's identity (login, session token)
- Attach user context (customer ID, account tier, tenant ID) to the request
- Handle session expiry

---

### 4. Chat Orchestrator (FastAPI)

The brain of the system. This is the service you are building.

**Current state:** A FastAPI app with `/` and `/health` endpoints.

**Future responsibilities:**
- Receive the customer message from the gateway
- Pass the message through the processing pipeline
- Coordinate between RAG, tools, and the LLM
- Send the final response back to the customer
- Store conversation data in PostgreSQL
- Cache recent responses in Redis

**Why FastAPI?**
- Fast to build and iterate
- Native async support for non-blocking I/O
- Automatic OpenAPI documentation
- Python ecosystem (ideal for ML and AI integrations)

---

### 5. Processing Pipeline

A sequence of operations applied to every customer message before a response is generated.

#### 5.1 PII Redaction and Input Guardrails

Runs before any AI model sees the message.

- Detects and masks personally identifiable information (credit card numbers, emails, phone numbers)
- Blocks prompt injection attempts (instructions hidden in user messages designed to hijack the AI)
- Flags abusive, fraudulent, or legally sensitive content

**Why first?**
You never want PII or injection attempts to reach the model logs or external services.

#### 5.2 NLU Service (Natural Language Understanding)

Analyses the customer's intent and extracts structured information.

| Output | Example |
|---|---|
| Intent | `refund_request` |
| Entities | `order_id: #12345`, `product: Premium Plan` |
| Sentiment | `negative`, `frustrated` |
| Urgency | `high` |
| Confidence | `0.87` |

The NLU output drives all downstream routing decisions.

#### 5.3 Agent Router / Planner

Decides what to do based on the NLU output.

| Condition | Action |
|---|---|
| High confidence + FAQ question | Route to RAG retrieval |
| Order/refund/ticket request | Route to MCP tool |
| Low confidence | Ask clarification or escalate |
| Fraud / legal / chargeback detected | Escalate to human immediately |
| Customer explicitly asks for human | Route to human handoff |

---

### 6. RAG Service (Retrieval-Augmented Generation)

Finds relevant information from your company's knowledge base before the LLM generates a response.

**Why RAG?**
An LLM alone does not know your refund policy, product docs, or help articles. RAG retrieves the relevant passages so the LLM can generate a grounded answer with citations instead of making things up.

**How it works:**

```
Customer question
      ↓
Convert to embedding vector
      ↓
Search vector database (semantic similarity)
      +
Keyword search (BM25)
      ↓
Merge and rerank results
      ↓
Return top 5 relevant chunks with source metadata
```

**Data sources:**
- Vector database — stores embedded document chunks (Pinecone, Qdrant, FAISS)
- Keyword search index — OpenSearch or Elasticsearch for BM25
- Object storage — original PDF/Word files (S3, GCS)

---

### 7. MCP Tool Layer (Model Context Protocol)

Standardises how the AI agent calls business tools and external APIs.

Each tool is exposed as an MCP server with a defined input/output schema.

| MCP Server | Available Tools |
|---|---|
| Order Server | `get_order_status`, `get_delivery_eta` |
| Refund Server | `check_refund_eligibility`, `start_refund_case` |
| Ticket Server | `create_ticket`, `update_ticket` |
| CRM Server | `get_customer_profile`, `update_customer_notes` |
| FAQ Server | `search_faq`, `get_policy_chunk` |

**Why MCP?**
MCP gives the LLM a safe, schema-defined way to call tools. The LLM cannot call arbitrary code — it can only use tools with defined inputs and outputs. This prevents unsafe or unintended actions.

---

### 8. LLM Service

Generates the final natural language response using:
- The customer's original message
- The NLU output (intent, entities)
- Retrieved RAG context (policy passages, FAQ answers)
- Tool results (order status, refund eligibility)

**Output is structured JSON:**
```json
{
  "intent": "refund_request",
  "confidence": 0.87,
  "response": "I checked your order and our refund policy...",
  "citations": ["refund_policy_v3.pdf#chunk_12"],
  "next_action": "create_ticket",
  "escalation_required": false
}
```

**Why structured output?**
Structured output makes it easy to extract citations, trigger follow-up actions, and audit what the model decided — without parsing free text.

---

### 9. Output Guardrails

Runs on the LLM's response before it reaches the customer.

**Checks performed:**
- Is the answer grounded in the retrieved context? (no hallucinations)
- Do the citations actually support the claims?
- Does the response violate any policy (e.g. promising a refund without eligibility check)?
- Does the response contain PII that should not be exposed?
- Is the confidence high enough to send automatically, or should it escalate?

If any check fails, the response is blocked and the case is escalated to a human.

---

### 10. Data Layer

| Store | Technology | What is stored |
|---|---|---|
| Relational DB | PostgreSQL | Conversations, messages, users, tickets, documents, feedback |
| Cache | Redis | Active sessions, recent FAQ responses, rate limit counters |
| Vector DB | Pinecone / Qdrant / FAISS | Document chunk embeddings for semantic search |
| Object Storage | S3 / GCS | Original uploaded PDFs, policy docs, FAQ files |
| Message Queue | Kafka / SQS | Async document ingestion jobs, embedding tasks |

---

### 11. Observability

Every step of the pipeline is logged and traced.

**What is tracked per conversation:**
```
conversation_id
user_id / tenant_id
intent + confidence score
retrieved chunk IDs and scores
prompt version used
model name and token count
latency per step
tool calls and outcomes
escalation reason (if any)
user feedback rating
```

**Dashboards:**
- Support Operations — deflection rate, CSAT, escalation rate
- AI Quality — hallucination rate, groundedness, feedback scores
- RAG Health — retrieval hit rate, empty result rate
- Tool Performance — success rate, latency, failure reasons
- Cost — tokens per conversation, cost per resolved case

---

## Deployment Architecture

```
GitHub Repository
      ↓ (merge to develop / main)
GitHub Actions (deployment.yml)
      ↓ (railway up)
Railway Cloud Platform
      ├── Development Environment  ← merged from develop
      ├── Testing Environment      ← manual / PR
      └── Production Environment  ← merged from main
```

Each Railway environment runs:
- The FastAPI app built from `app/main.py`
- Python packages from `requirements.txt`
- Start command from `railway.toml`

See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for the full deployment setup guide.

---

## Current State vs Target State

| Component | Current State | Target State |
|---|---|---|
| Health API | Built and deployable | Stable |
| Chat Orchestrator | Skeleton (FastAPI app) | Full pipeline wired |
| NLU Service | Not built | Intent classifier + entity extraction |
| RAG Service | Not built | Hybrid search with reranking |
| MCP Tool Layer | Not built | Order, refund, ticket, CRM tools |
| LLM Service | Not built | Structured output with citations |
| Output Guardrails | Not built | Grounding + policy checks |
| Observability | Not built | OpenTelemetry + dashboards |
| Admin Console | Not built | Document upload + dashboard |

---

## Technology Decisions

| Decision | Choice | Reason |
|---|---|---|
| Web framework | FastAPI | Fast, async, Python-native, auto-docs |
| Hosting | Railway | Simple setup, environment management, GitHub integration |
| CI/CD | GitHub Actions | Already integrated with GitHub, no extra tooling |
| Build system | Nixpacks (Railway default) | Auto-detects Python, zero Docker config needed |
| Agent orchestration | LangGraph (planned) | Stateful agent graphs, reliable multi-step workflows |
| MCP | Anthropic MCP SDK (planned) | Standardised tool interface for LLM agents |
