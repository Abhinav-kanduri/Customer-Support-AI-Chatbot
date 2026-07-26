# Feature 5: Feedback, Evaluation, and Observability

## Objective

Replace demo-only dashboard values with captured pipeline events and create the
minimum feedback and evaluation loop needed to operate the chatbot safely.

## Architecture alignment

This implements the first slice of the architecture's observability layer and
turns the existing RAG dashboard into a live operational view.

## Scope

Included:

- Message-linked positive/negative feedback
- Structured application events
- Trace/run correlation
- Model, prompt, tokens, retries, and latency fields
- Versioned evaluation suites/cases/runs/results
- Daily pipeline and feedback metric views
- Conversion of the demo dashboard to clearly separated live data

Full OpenTelemetry infrastructure, SIEM export, automated retraining, and A/B
deployment remain future work.

## Metrics to capture

### Per request

- Trace ID, conversation ID, and message ID
- Intent, confidence, route, and escalation reason
- Retrieval chunk IDs, scores, and result count
- Model and prompt version
- Input/output token counts
- Latency for NLU, retrieval, generation, guardrails, and total request
- Dependency errors and retry count
- Final outcome: answered, clarified, escalated, or failed

### Aggregated

- Request and successful-answer volume
- Escalation and clarification rates
- Retrieval hit and empty-result rates
- Guardrail block rate
- Error rate by dependency
- Latency percentiles
- Positive/negative feedback rate
- Token usage and estimated cost

## Planned feedback API

`POST /v1/feedback`

```json
{
  "conversation_id": "conv_...",
  "message_id": "msg_...",
  "rating": "positive",
  "reason": "answered_my_question",
  "comment": "optional comment"
}
```

The endpoint must prevent duplicate active feedback for the same user/message or
define clear update semantics.

Recommended update behavior:

- First submission creates active feedback.
- A later submission by the same subject supersedes the old row and creates a new
  active row, preserving audit history.
- Removal marks a row `removed`; it does not physically delete operational history
  unless required by an approved privacy request.
- The service verifies that the target message is an assistant message visible to
  the submitting user.

## Database fields

### `feedback`

Stores conversation/message/user links, a stable authenticated-user or hashed
session `submission_key`, positive or negative rating, reason code, redacted
comment, optional resolution flag, active/superseded/removed status, and
timestamps. The submission key makes the one-active-feedback rule work even when
the optional user FK is unavailable.

### `application_events`

| Column group | Purpose |
|---|---|
| Trace/run/conversation/message IDs | End-to-end correlation |
| Event name/category/status | Stable operational classification |
| Duration and retry count | Reliability/latency analysis |
| Model/prompt versions | Reproducibility |
| Input/output tokens | Usage and cost analysis |
| Error code | Sanitized failure aggregation |
| `attributes_safe` JSONB | Bounded stage-specific metadata |
| `created_at` | Time-series ordering |

The event table must not become a copy of prompts, responses, retrieved chunks, or
raw third-party errors. Those belong in their governed source tables.

### Evaluation tables

- `evaluation_suites`: named/versioned golden datasets
- `evaluation_cases`: redacted input, expected intent/route/sources/facts/escalation
- `evaluation_runs`: code SHA, safe model config, status, totals, aggregate metrics
- `evaluation_results`: actual outputs, metric values, pass state, failure reasons

### Dashboard views

- `pi1_daily_pipeline_metrics`: request outcomes plus P50/P95 latency
- `pi1_daily_feedback_metrics`: active feedback and positive/negative counts

Views are intentionally simple baselines. Expensive or high-volume aggregates may
become materialized views after measurement.

## DDL

Draft migration:
[sql/005_feedback_observability.sql](sql/005_feedback_observability.sql)

Indexes cover trace/run lookup, event category/status, event name, JSON attributes,
feedback rating, evaluation suite history, and dashboard date ranges.

## Event naming contract

Use stable dotted names:

```text
api.chat.received
nlu.inference.completed
routing.decision.completed
retrieval.search.completed
generation.response.completed
guardrail.output.blocked
escalation.case.created
feedback.submitted
dependency.openai.failed
```

High-cardinality values such as full messages, queries, stack traces, and user
emails must not be used as event names or metric labels.

## Retention proposal

| Data | Initial proposal |
|---|---|
| Application events | 90 days online, then aggregate/archive |
| Feedback | Product/privacy policy duration |
| Evaluation records | Retain by suite/model version |
| Safe error details | 30-90 days |
| Raw/unredacted content | Not stored by this feature |

Final retention requires product, security, and legal approval.

## Evaluation scope

Create a versioned golden set containing:

- Customer question
- Expected intent and route
- Expected source document/chunk or answer facts
- Expected escalation decision
- Safety tags

Run it in CI without calling live production services. A separately triggered
integration evaluation may call configured external services and store results.

## Implementation tasks

1. Define a structured application-event schema.
2. Add trace IDs and timed spans around each pipeline stage.
3. Store operational events and customer feedback.
4. Ensure logs redact PII and never contain API keys or database credentials.
5. Add health/readiness checks for model artifacts, database, and OpenAI access.
6. Connect the existing dashboard to real aggregated data.
7. Mark or remove all dummy metrics from the live view.
8. Add a golden-set evaluation runner and baseline report.
9. Define initial alert thresholds for elevated errors, latency, and escalations.

## Acceptance criteria

- Every chat response contains a trace ID that can be found in operational data.
- Per-stage latency and final pipeline outcome are recorded.
- Feedback is linked to an existing assistant message.
- Dashboard totals reconcile with stored pipeline events for a selected time range.
- No generated/demo values appear as live production metrics.
- Logs and feedback exports pass the configured secret/PII checks.
- The golden-set runner reports intent, routing, retrieval, citation, and escalation
  pass rates.
- A failing quality threshold produces a clear CI/evaluation failure.
- Event-category and status values are database constrained.
- Feedback cannot target a missing or unauthorized message.
- Dashboard queries use real stored events and identify their selected time window.
- Evaluation results retain the code/model configuration needed to reproduce a run.

## Test plan

- Trace propagation across every Feature 1-4 stage
- Duplicate, superseded, removed, and unauthorized feedback
- Event schema and PII/secret rejection tests
- P50/P95 view reconciliation against known fixtures
- Golden-set pass/fail threshold tests
- Evaluation run interruption and partial-result handling
- Dashboard empty-state, time-zone, and high-volume query tests

## Dependencies

- Events emitted by Features 1-4
- Data-retention and access-control decisions
- A reviewed initial golden dataset

## Out of scope

- Full OpenTelemetry collector infrastructure
- Enterprise SIEM integration
- Automated model retraining
- Advanced A/B or canary prompt deployment

## Estimate

Medium to large. Instrumentation should be implemented alongside Features 1-4;
dashboard conversion and evaluation reporting complete this feature.
