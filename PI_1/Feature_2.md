# Feature 2: NLU Integration and Decision Router

## Objective

Integrate the existing restaurant intent classifier into the backend, add entity
and urgency extraction, and select a deterministic route for every customer
message.

## Architecture alignment

This implements the NLU Service and Agent Router described in the architecture.
The trained Streamlit model becomes a reusable backend service instead of remaining
only inside a standalone UI.

## Scope

Included:

- Shared model-loading and inference service
- Fixed 24-intent output validation
- Deterministic entity extraction for approved entity types
- Sentiment and urgency signals
- Versioned routing policy
- Auditable route decision and reason
- Safe fallback when the model is unavailable

The classifier remains advisory. Code-owned routing policy decides whether the
system retrieves, clarifies, responds directly, or hands off.

## Planned NLU output

```json
{
  "intent": "ORDER_STATUS",
  "confidence": 0.91,
  "entities": {
    "order_id": "12345"
  },
  "sentiment": "neutral",
  "urgency": "normal",
  "route": "rag",
  "escalation_reason": null
}
```

## Routing rules

| Condition | Route |
|---|---|
| High-confidence informational question | `rag` |
| Explicit human-agent request | `human` |
| High-risk food safety, fraud, legal, or chargeback intent | `human` |
| Confidence below configured threshold | `clarify` or `human` |
| Order/refund/tool intent without a production tool | `human` |
| Unsupported or out-of-domain intent | `clarify` |

Thresholds and high-risk intent lists must live in configuration, not be scattered
through route code.

## Entity contract

The `entities` JSON object may contain only allowlisted keys in PI-1:

| Key | Value format | Storage rule |
|---|---|---|
| `order_id` | Normalized string | Store when not treated as sensitive |
| `invoice_id` | Normalized string | Store redacted/hashed when policy requires |
| `amount` | Decimal plus currency | Never include payment-card data |
| `date` | ISO-8601 date | Store normalized |
| `product_name` | String | Store redacted if user-provided PII is detected |
| `email_token` | Replacement token | Never store the source email here |
| `phone_token` | Replacement token | Never store the source phone number here |

Unknown keys are rejected or moved to a reviewed safe metadata area.

## Database fields

### `routing_policies`

Stores a versioned policy name/version, activation state, low/high confidence
thresholds, high-risk intents, intent-to-route mapping, safe JSON configuration,
creator, and activation timestamps. A partial unique index permits only one active
version per policy name.

### `nlu_results`

| Column | Type | Purpose |
|---|---|---|
| `nlu_result_id` | `uuid` PK | Prediction record |
| `run_id` | `uuid` unique FK | One NLU result per pipeline run |
| `model_name`, `model_version` | `text` | Artifact lineage |
| `intent_code` | `text` | Validated intent |
| `intent_confidence` | `numeric(7,6)` | Bounded 0-1 score |
| `entities` | `jsonb` | Allowlisted normalized entities |
| `sentiment`, `sentiment_score` | Mixed | Categorical and bounded -1 to 1 signal |
| `urgency` | `text` check | Low, normal, high, or critical |
| `department` | `text` | Support ownership mapping |
| `recommended_action` | `text` | Advisory next step |
| `escalation_suggested` | `boolean` | Classifier/mapping signal |
| `inference_latency_ms` | `integer` | Non-negative model latency |
| `created_at` | `timestamptz` | Audit timestamp |

### `routing_decisions`

Stores the selected route, reason code, safe explanation, policy version, threshold
snapshot, and high-risk flag. Keeping the snapshot makes historical decisions
explainable after policy thresholds change.

## DDL

Draft migration: [sql/002_nlu_routing.sql](sql/002_nlu_routing.sql)

Key indexes support intent-volume analysis, low-confidence review, JSON entity
queries, route queues, and reason-code reporting.

## Model lifecycle

1. Validate artifact existence, checksum, metadata, and supported classes at startup.
2. Load the model once per worker.
3. Expose model readiness without revealing filesystem details.
4. Record model name/version on every inference.
5. Fall back to `clarify` or `human` if readiness or inference fails.
6. Promote a new artifact only after golden-set and adversarial evaluation.

## Implementation tasks

1. Extract model loading and prediction logic from the Streamlit app into a shared
   `app/services/nlu.py` module.
2. Load the model once per process and expose readiness status.
3. Normalize intent names and validate them against an allowed enum.
4. Extract common entities such as order ID, email, date, amount, and product name
   using deterministic patterns first.
5. Add sentiment and urgency signals with a documented confidence policy.
6. Implement a pure, testable decision-router function.
7. Attach NLU results to the Feature 1 response and pipeline record.
8. Record model version, classifier confidence, and routing reason.

## Acceptance criteria

- All 24 supported restaurant intents map to a known department and route.
- The same NLU input and configuration produce the same route decision.
- High-risk and explicit-human messages always route to human review.
- Low-confidence predictions never silently produce a confident automated answer.
- Extracted PII is not copied into logs in clear text.
- Missing or corrupt model artifacts fail readiness checks and trigger a safe
  fallback instead of crashing the API.
- Unit tests cover each routing branch and threshold boundary.
- Only one routing-policy version is active for a policy name.
- Historical decisions retain their policy and threshold snapshot.
- Confidence values outside 0-1 are rejected at both model and database boundaries.
- Entity output never contains raw email, phone, credential, or card values.

## Test plan

- One test per supported intent and department mapping
- Exact low/high threshold boundary tests
- High-risk override tests regardless of classifier confidence
- Corrupt/missing artifact and inference-time failure tests
- Entity normalization, overlapping matches, and PII-token tests
- Determinism test for identical input, model, and policy versions
- Database constraints for invalid confidence, sentiment, urgency, and route values

## Dependencies

- Feature 1 structured pipeline and persistence
- Existing classifier artifacts
- Agreed confidence thresholds and escalation policy

## Out of scope

- Retraining the model on production messages
- Multilingual classification
- Automatic execution of order or refund actions

## Estimate

Medium. The existing model reduces initial build effort, but production-safe
confidence handling and routing tests are required.
