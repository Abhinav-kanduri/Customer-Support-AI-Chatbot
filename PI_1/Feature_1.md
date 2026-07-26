# Feature 1: Conversation Orchestrator and Session Logging

## Objective

Replace the current single-prompt chat call with a stateful orchestration endpoint
that creates conversations, stores messages, and returns a stable structured
response for all later pipeline stages.

## Architecture alignment

This implements the architecture's Chat Orchestrator, short-term memory, and
relational conversation store. It becomes the entry point for NLU, RAG,
guardrails, escalation, and observability.

## Scope

Included:

- Versioned chat endpoint
- Conversation creation and continuation
- Customer and assistant message persistence
- Bounded conversation history
- Pipeline run and trace IDs
- Idempotent client retry behavior
- Conversation read API with ownership/RBAC checks

Not included:

- NLU, retrieval, guardrails, and feedback logic owned by Features 2-5
- Redis caching
- WebSocket/streaming responses
- Enterprise multi-tenant isolation

## User stories

- As a customer, I can continue a support conversation without repeating its
  context.
- As a support agent, I can inspect the messages and decisions associated with a
  conversation.
- As a developer, I receive a stable response schema instead of unstructured model
  text.

## Planned API

### Create or continue a chat

`POST /v1/chat`

```json
{
  "conversation_id": "optional-existing-id",
  "message": "Where is my order?",
  "user_id": "optional-user-id"
}
```

Initial response contract:

```json
{
  "conversation_id": "conv_...",
  "message_id": "msg_...",
  "response": "Support response",
  "intent": null,
  "confidence": null,
  "citations": [],
  "next_action": "respond",
  "escalation_required": false,
  "trace_id": "trace_..."
}
```

Fields populated by later features remain present with safe defaults.

### Read conversation history

`GET /v1/conversations/{conversation_id}`

Returns conversation metadata and ordered customer/assistant messages. Access must
be limited to the conversation owner or an authorized support role.

### API behavior and errors

| Condition | Status | Behavior |
|---|---|---|
| New valid message | `200` or `201` | Creates conversation when needed and starts a pipeline run |
| Empty/oversized message | `422` | Returns field-level validation details |
| Conversation not found | `404` | Does not reveal unrelated conversation data |
| Authenticated user is not owner/agent | `403` | Access denied and security event recorded |
| Reused key with same request | Original status | Returns stored response without duplicate work |
| Reused key with different request | `409` | Reports idempotency-key conflict |
| Database unavailable | `503` | Sanitized message and trace ID |

The API should accept an `Idempotency-Key` header for message creation.

## Data changes

Create migrations for:

- `conversations`: ID, user ID, status, timestamps, last intent, assigned agent
- `messages`: ID, conversation ID, role, original text, safe text, response text,
  model, token counts, timestamps
- `pipeline_runs`: trace ID, conversation ID, message ID, status, total latency,
  error code, timestamps

Do not store secrets. The original message retention policy must be configurable.

## Database fields

### `support_users`

| Column | Type | Purpose |
|---|---|---|
| `user_id` | `uuid` PK | Internal stable identity |
| `external_subject` | `text` unique | OIDC/Supabase identity subject |
| `email_hash` | `text` | Lookup/deduplication without raw email |
| `display_name` | `text` | Optional agent/customer display label |
| `user_role` | `text` check | Customer, agent, admin, or auditor |
| `user_status` | `text` check | Pending, active, disabled, or deleted |
| `preferences` | `jsonb` | Locale/channel preferences |
| `created_at`, `updated_at` | `timestamptz` | Lifecycle timestamps |
| `last_login_at` | `timestamptz` | Authentication audit signal |

This table does not store passwords. The legacy `app_users` password flow must be
retired or migrated through an approved authentication design.

### `conversations`

| Column | Type | Purpose |
|---|---|---|
| `conversation_id` | `uuid` PK | Public conversation identifier |
| `customer_user_id` | `uuid` FK | Conversation owner |
| `assigned_agent_id` | `uuid` FK | Current human owner |
| `channel` | `text` check | API, web, mobile, email, or internal |
| `conversation_status` | `text` check | Open/waiting/escalated/resolved/closed lifecycle |
| `last_intent` | `text` | Denormalized queue/search field |
| `locale` | `text` | Response locale |
| `metadata` | `jsonb` | Non-sensitive extensible context |
| Lifecycle timestamps | `timestamptz` | Created, updated, last message, closed |

### `messages`

| Column | Type | Purpose |
|---|---|---|
| `message_id` | `uuid` PK | Stable message identifier |
| `conversation_id` | `uuid` FK | Owning conversation |
| `sender_user_id` | `uuid` FK | Customer/agent sender when applicable |
| `parent_message_id` | `uuid` FK | Customer message answered by an assistant message |
| `message_role` | `text` check | Customer, assistant, agent, system, or tool |
| `content_redacted` | `text` | Default safe stored content |
| `content_encrypted` | `bytea` | Optional approved original-content storage |
| `content_sha256` | `text` | Integrity/deduplication aid |
| Model/prompt/token fields | Mixed | Generation audit and cost data |
| `message_status` | `text` check | Received, processing, stored, blocked, or failed |
| `metadata` | `jsonb` | Safe structured message attributes |
| `created_at` | `timestamptz` | Immutable ordering timestamp |

### `pipeline_runs`

One row represents one customer-message pipeline execution. It stores `run_id`,
unique `trace_id`, conversation/customer/assistant message links, run status,
final outcome, selected route, safe error information, total latency, and start/end
timestamps.

### `idempotency_records`

Stores the caller/key/path tuple, request hash, processing state, original response,
and expiry. The request hash prevents the same key from being reused for a
different payload.

## DDL

Draft migration:
[sql/001_conversation_orchestrator.sql](sql/001_conversation_orchestrator.sql)

Important indexes:

- Conversation history: `(conversation_id, created_at, message_id)`
- Customer conversation list: `(customer_user_id, created_at DESC)`
- Agent queue: `(assigned_agent_id, conversation_status)`
- Trace lookup: unique `trace_id`
- Retry cleanup: `idempotency_records(expires_at)`

## State transitions

```text
conversation: open -> waiting_customer | waiting_agent | escalated
             -> resolved -> closed

pipeline run: started -> completed | escalated | failed

message: received -> processing -> stored
         processing -> blocked | failed
```

Invalid transitions should be rejected in the service layer and covered by tests.

## Implementation tasks

1. Add versioned request and response Pydantic models.
2. Add a conversation repository layer instead of embedding SQL in routes.
3. Create or load conversation context with a bounded message window.
4. Store the customer message before processing.
5. Store the assistant response and pipeline outcome atomically where practical.
6. Add idempotency handling to prevent duplicate messages on client retry.
7. Keep the existing `/chat` route temporarily or document its migration path.
8. Add unit and API integration tests.

## Acceptance criteria

- A request without a conversation ID creates one.
- A request with a valid conversation ID appends to that conversation.
- Conversation history is returned in chronological order.
- Invalid or unauthorized conversation IDs do not expose stored messages.
- Repeating the same idempotency key does not create a duplicate message.
- Database failure returns a sanitized service error with a trace ID.
- The response contract remains valid even when a downstream stage fails.
- Conversation history uses a deterministic `(created_at, message_id)` order.
- Closing a conversation records `closed_at`.
- Raw credentials, API keys, and payment data never enter message metadata.
- The schema supports deleting a conversation and its dependent operational data
  according to the approved retention policy.

## Test plan

- Repository tests for create, append, list, close, and delete behavior
- Concurrent requests using the same idempotency key
- Ownership and agent/admin authorization matrix
- Transaction rollback when message or pipeline-run insertion fails
- Pagination and bounded-history tests for long conversations
- Retention test proving encrypted/original content is optional

## Dependencies

- Existing FastAPI application and PostgreSQL connection
- Database migration process
- Authentication improvements for conversation ownership

## Estimate

Medium. This should be completed first because every other PI 1 feature attaches to
the orchestrator and its audit records.
