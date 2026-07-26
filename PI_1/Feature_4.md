# Feature 4: Guardrails and Human Handoff

## Objective

Protect the pipeline before and after model execution and create a reliable human
handoff whenever automation is unsafe, unsupported, or uncertain.

## Architecture alignment

This implements the architecture's PII redaction, input guardrails, output
guardrails, escalation policy, and human-in-the-loop behavior.

## Scope

Included:

- Versioned guardrail configuration
- Input, retrieval, and output check events
- PII detection metadata without detected values
- Idempotent escalation-case creation
- Role-protected queue, detail, assignment, and status APIs
- Immutable case event history

No automated refund, credit, order mutation, or external ticket-provider write is
allowed in PI-1.

## Input controls

- Validate message size and supported content type.
- Detect and mask email addresses, phone numbers, payment-card patterns, and other
  configured PII before external model calls and logging.
- Detect common prompt-injection patterns and untrusted instructions.
- Identify abuse, fraud, food safety, legal threats, chargebacks, and explicit
  human-agent requests.
- Rate-limit repeated requests by user/session.

PII masking must preserve useful references, for example
`john@example.com -> [EMAIL_1]`, without exposing the original value in logs.

## Output controls

- Confirm the answer is supported by retrieved context when RAG was used.
- Confirm all citations exist and support the response.
- Block unauthorized promises, such as guaranteeing refunds or compensation.
- Scan generated output for leaked PII or internal instructions.
- Apply confidence and retrieval-score thresholds.
- Replace unsafe output with a safe handoff response.

## Escalation record

Create or extend an escalation/case table with:

- Case ID and conversation ID
- Customer message ID
- Escalation reason code and severity
- Intent, confidence, and retrieval result summary
- Safe conversation summary
- Assignment and status
- Created, acknowledged, and resolved timestamps
- Audit trail of status changes

Do not copy unmasked sensitive content into the escalation summary.

## Planned APIs

- `GET /v1/escalations` with status, severity, assignee, and date filters
- `GET /v1/escalations/{case_id}`
- `PATCH /v1/escalations/{case_id}` for assignment and status changes

Changes require an authenticated support/admin role and must be audited.

## Escalation API fields

`PATCH /v1/escalations/{case_id}` should accept only allowlisted transitions:

```json
{
  "case_status": "in_review",
  "assigned_agent_id": "00000000-0000-0000-0000-000000000000",
  "note_safe": "Reviewing the policy exception."
}
```

The caller cannot directly overwrite the original reason, source message, creation
time, or audit history.

## Database fields

### `guardrail_policies`

Stores policy name/version, one-active-version flag, safe JSON configuration,
creator, and activation time.

### `guardrail_events`

| Column | Type | Purpose |
|---|---|---|
| `guardrail_event_id` | `uuid` PK | Individual check |
| `run_id`, `message_id` | UUID FKs | Pipeline/message context |
| `guardrail_policy_id` | `uuid` FK | Exact policy version |
| `guardrail_stage` | `text` check | Input, retrieval, or output |
| `check_type` | `text` | PII, injection, citation, policy, etc. |
| `check_result` | `text` check | Pass, block, review, or error |
| `severity` | `text` check | Info through critical |
| `reason_code` | `text` | Stable analytics code |
| `details_safe` | `jsonb` | Redacted diagnostic metadata |
| `check_latency_ms` | `integer` | Check performance |

### `pii_detections`

Stores PII type, replacement token, character offsets, detector version, and
confidence. It intentionally has no column for the detected raw value.

### `escalation_cases`

Stores conversation/source message/run links, reason, severity, status, safe
summary, intent/confidence snapshot, assigned agent, priority score, resolution,
safe metadata, and lifecycle timestamps. A unique source-message constraint makes
case creation idempotent.

### `escalation_events`

Append-only audit history with actor, event type, before/after status, safe note,
metadata, and timestamp.

## DDL

Draft migration:
[sql/004_guardrails_escalation.sql](sql/004_guardrails_escalation.sql)

Queue indexes support status/severity ordering and assigned-agent worklists.

## Allowed case transitions

```text
open -> assigned -> in_review
in_review -> waiting_customer | resolved
waiting_customer -> in_review
resolved -> closed | reopened
closed -> reopened (admin/approved policy only)
```

Every transition writes `escalation_events` in the same transaction. Assignment,
acknowledgment, resolution, and closure timestamps must be derived by the service,
not trusted from the client.

## Implementation tasks

1. Define guardrail result and escalation-reason enums.
2. Build pre-processing PII masking and message validation.
3. Add prompt-injection and high-risk routing rules.
4. Build post-generation citation, policy, and PII checks.
5. Centralize the escalation decision in one policy service.
6. Persist escalation cases idempotently.
7. Add role-protected case-management endpoints.
8. Return a consistent, customer-safe handoff message.
9. Add adversarial, boundary, and authorization tests.

## Acceptance criteria

- Configured PII is masked before model calls and application logs.
- Explicit human requests and high-risk categories always create a handoff.
- Low-confidence or ungrounded answers are never sent as confident resolutions.
- Reprocessing the same message does not create duplicate escalation cases.
- Only authorized support roles can view or change escalation details.
- Every escalation state change has an actor and timestamp.
- Tests prove that prompt injection cannot override system routing or tool policy.
- PII detection rows cannot contain detected source values.
- Invalid case-state transitions return `409` and do not change the case.
- Case creation and its initial audit event commit atomically.
- Agent queue queries use the planned composite indexes.

## Test plan

- Email, phone, card-pattern, secret, and false-positive redaction fixtures
- Prompt-injection and retrieved-content injection tests
- Grounding/citation/policy check pass and block paths
- One test for every allowed and rejected escalation transition
- Concurrent duplicate case creation for one source message
- Customer/agent/admin/auditor permission matrix
- Audit-event immutability and safe-note validation

## Dependencies

- Features 1-3 pipeline outputs
- Authentication/role enforcement
- Approved escalation reasons, severities, and response wording

## Out of scope

- Automated refunds or financial actions
- External Zendesk/CRM synchronization
- Advanced ML-based PII recognition beyond the documented PI 1 detector set

## Estimate

Large because safety and authorization require negative-path and adversarial
testing, not only successful-flow tests.
