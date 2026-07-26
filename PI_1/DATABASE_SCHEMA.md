# PI-1 Database Schema Specification

## Status

This is the logical and physical schema proposal for PI-1. The executable draft
DDL is in `PI_1/sql`. It has not been applied to development, testing, or
production by this documentation change.

## Design conventions

| Convention | Decision |
|---|---|
| Database | PostgreSQL/Supabase |
| Vector extension | pgvector |
| UUID generation | `pgcrypto.gen_random_uuid()` |
| New operational IDs | Native `uuid` |
| Existing document IDs | `text` for `doc_...`/`chunk_...` compatibility |
| Time | `timestamptz`, stored and compared in UTC |
| Extensible metadata | JSONB with object/array check constraints |
| PII | Redacted by default; raw detected values excluded from telemetry |
| Deletion | Explicit FK actions based on record ownership/audit needs |
| Schema evolution | Ordered, reviewed, version-controlled migrations |

## Table ownership by feature

| Feature | Tables/views/functions |
|---|---|
| Feature 1 | `support_users`, `conversations`, `messages`, `pipeline_runs`, `idempotency_records`, `pi1_set_updated_at()` |
| Feature 2 | `routing_policies`, `nlu_results`, `routing_decisions` |
| Feature 3 | `documents`, `document_chunks`, `retrieval_events`, `retrieval_results`, `response_citations`, `match_document_chunks()` |
| Feature 4 | `guardrail_policies`, `guardrail_events`, `pii_detections`, `escalation_cases`, `escalation_events` |
| Feature 5 | `feedback`, `application_events`, `evaluation_suites`, `evaluation_cases`, `evaluation_runs`, `evaluation_results`, daily metric views |

## Relationship summary

```text
support_users
  +-- conversations
  |     +-- messages
  |     |     +-- pipeline_runs
  |     |     |     +-- nlu_results
  |     |     |     |     +-- routing_decisions
  |     |     |     +-- retrieval_events
  |     |     |     |     +-- retrieval_results
  |     |     |     +-- guardrail_events
  |     |     |     +-- application_events
  |     |     +-- response_citations
  |     |     +-- feedback
  |     +-- escalation_cases
  |           +-- escalation_events
  +-- routing_policies / guardrail_policies

documents
  +-- document_chunks
        +-- retrieval_results
              +-- response_citations

evaluation_suites
  +-- evaluation_cases
  +-- evaluation_runs
        +-- evaluation_results
```

## Key integrity rules

- A message cannot exist without a conversation.
- A pipeline run starts from exactly one customer message.
- One customer message has at most one pipeline run in PI-1.
- One pipeline run has at most one NLU result and one routing decision.
- Retrieval rank and chunk are unique inside one retrieval event.
- A citation can reference only a persisted retrieval result.
- One source message creates at most one escalation case.
- Every escalation case transition is appended to `escalation_events`.
- One active routing and guardrail policy version exists per policy name.
- One active feedback record exists per message and submission key.

## Delete behavior

| Parent deletion | Planned effect |
|---|---|
| Conversation | Cascades messages, pipeline-owned operational records, and feedback |
| User | Usually sets ownership/actor FKs to null; idempotency records are removed |
| Message | Cascades message-owned runs/citations/feedback where permitted |
| Document chunk | Restricted when retrieval audit records reference it |
| Retrieval event | Cascades its ranked results |
| Escalation case | Cascades case events; application service should normally archive instead |
| Evaluation suite | Cases cascade; completed run references are restricted |

Physical deletion must still obey legal hold, audit, and privacy requirements.
Operational services should prefer status changes for escalation and feedback
records rather than casual deletion.

## JSONB contracts

JSONB is not an unbounded dumping area. Application validation must define allowed
keys and maximum serialized size.

| Field | Example allowed content |
|---|---|
| `conversations.metadata` | Campaign/source/channel attributes without PII |
| `nlu_results.entities` | Normalized order/date/product fields and PII tokens |
| `routing_policies.intent_route_map` | Intent-to-route configuration |
| `documents.metadata` | Region, product, audience, access classification |
| `retrieval_events.applied_filters` | Document type, region, active version |
| `guardrail_events.details_safe` | Detector code and safe diagnostic flags |
| `application_events.attributes_safe` | Result count, dependency name, safe stage fields |
| Evaluation JSON fields | Expected/actual document IDs, facts, tags, metrics |

## Access-control proposal

| Data | Customer | Support agent | Admin | Auditor |
|---|---|---|---|---|
| Own conversation/messages | Read | Assigned/read by policy | Read | Redacted read |
| Other customer conversations | No | Only assigned/queue-authorized | Read | Redacted read |
| Routing/guardrail policies | No | Read active | Manage | Read |
| Documents/chunks | Published citations only | Read authorized | Manage | Read metadata |
| Escalation cases | Own safe status | Assigned queue/update | Manage | Read audit |
| Feedback | Own create/update | Read aggregated | Read/manage policy | Read audit |
| Application events | No | Limited case trace | Operational read | Redacted audit |
| Evaluation data | No | Limited results | Manage | Read |

If Supabase clients access tables directly, row-level security must enforce these
rules. If only FastAPI accesses PostgreSQL, use a restricted service role and
enforce the same policy in tested repository/service boundaries.

## Migration readiness checklist

- Inventory the live definitions of `documents`, `document_chunks`, `app_users`,
  and `escalated_table`.
- Decide whether `support_users` replaces or maps to legacy `app_users`.
- Backfill document metadata and active/version values.
- Identify orphan `document_chunks.doc_id` values before adding a document FK.
- Confirm every stored vector has 1,536 dimensions.
- Confirm pgvector and pgcrypto are permitted in every Supabase/Railway environment.
- Test indexes with `EXPLAIN (ANALYZE, BUFFERS)` on representative data.
- Define retention and encryption-key ownership before using `content_encrypted`.
- Add migration history, backups, smoke tests, and a reviewed rollback procedure.
- Apply migrations with least privilege and never directly from an unreviewed app
  startup path.

