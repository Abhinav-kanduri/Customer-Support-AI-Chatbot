# Feature 3: RAG Retrieval, Grounded Responses, and Citations

## Objective

Connect the existing embedded document chunks to chat so informational questions
are answered from the support knowledge base with traceable citations.

## Architecture alignment

This implements the first production slice of the RAG Service and LLM Service:
query embedding, vector retrieval, context assembly, structured model output, and
citation validation.

## Scope

Included:

- pgvector query embedding and cosine similarity search
- Active-document and document-type filtering
- Ranked result persistence
- Context selection and token budgeting
- Structured answer generation
- Citation persistence and validation
- Safe behavior for empty or low-quality retrieval

BM25, OpenSearch, cross-encoder reranking, object storage, and asynchronous
ingestion remain outside PI-1.

## Planned request flow

```text
NLU route = rag
    -> create query embedding
    -> pgvector similarity search
    -> filter and rank chunks
    -> assemble bounded context
    -> generate structured answer
    -> validate cited chunk IDs
    -> return answer and citations
```

## Planned internal retrieval API

`POST /v1/search`

```json
{
  "query": "What is the refund policy?",
  "top_k": 5,
  "document_type": null
}
```

```json
{
  "results": [
    {
      "doc_id": "doc_...",
      "chunk_id": "chunk_...",
      "document_name": "refund-policy.pdf",
      "content": "Relevant policy text",
      "score": 0.84
    }
  ]
}
```

## Chat output requirements

The LLM must return validated structured data containing:

- Answer text
- Cited document and chunk IDs
- Whether sufficient information was found
- Suggested next action
- Escalation flag

Only retrieved chunks may be cited. If retrieval does not meet the configured
quality threshold, the system must ask a clarifying question or escalate instead
of inventing an answer.

## Data and schema changes

- Add source metadata and optional page number/section fields to document chunks.
- Add a vector-search SQL function or parameterized pgvector query.
- Record the query, retrieved chunk IDs, similarity scores, rank, and retrieval
  latency in a retrieval audit table.
- Add document version and active/inactive state so outdated policies can be
  excluded.

## Database fields

### `documents`

The migration preserves current field names used by `app/routes/documents.py` and
adds production metadata.

| Column | Type | Purpose |
|---|---|---|
| `doc_id` | `text` PK | Existing `doc_...` identifier |
| `doc_nm`, `doc_type` | `text` | Display name and filter type |
| `doc_raw_text` | `text` | Extracted source text; retention must be reviewed |
| `doc_status` | `text` | Ingestion lifecycle |
| `document_version` | `text` | Source-policy version |
| `mime_type`, `source_uri` | `text` | Source metadata |
| `checksum_sha256` | `text` | Duplicate/version detection |
| `is_active` | `boolean` | Retrieval eligibility |
| `metadata` | `jsonb` | Region, product, audience, or access metadata |
| `created_by` | `uuid` FK | Uploading admin |
| Creation/update timestamps | `timestamptz` | Lifecycle audit |

### `document_chunks`

Existing text/vector fields remain. Added fields include chunk order, page number,
section title, token count, embedding model/dimensions, active state, and JSON
metadata. The HNSW cosine index remains the vector-search index.

### `retrieval_events`

One row records a query attempt: pipeline run, source message, redacted query,
embedding model, top-K, minimum similarity, filters, result count, status, latency,
safe error code, and timestamps.

### `retrieval_results`

One row per ranked chunk stores its retrieval event, chunk FK, rank, similarity
score, and whether it entered the model context. Unique constraints prevent a
chunk or rank from appearing twice in one retrieval event.

### `response_citations`

Links an assistant message to a retrieved result, preserves citation order and an
optional cited-text snapshot, and records pending/valid/invalid/unsupported
validation state.

## Vector-search DDL

Draft migration: [sql/003_rag_retrieval.sql](sql/003_rag_retrieval.sql)

It defines:

```sql
public.match_document_chunks(
    p_query_embedding vector(1536),
    p_result_limit integer,
    p_minimum_similarity double precision,
    p_doc_type text
)
```

The function returns chunk/source fields and `1 - cosine_distance` as similarity.
It caps results at 50 and excludes inactive documents and chunks.

## Ingestion and retrieval states

```text
document: RECEIVED -> PROCESSING -> CHUNKED -> EMBEDDED
          any processing step -> FAILED

retrieval: started -> completed | empty | failed

citation: pending -> valid | invalid | unsupported
```

Only `EMBEDDED`/active documents should be eligible for production retrieval; the
service query must enforce status as well as active state before release.

## Context-assembly rules

- Sort by similarity before any secondary reranking.
- Deduplicate overlapping chunks from the same document.
- Preserve source metadata and original rank.
- Enforce maximum chunks and token budget.
- Do not include inactive, unauthorized, or below-threshold chunks.
- Record every candidate and whether it was selected for context.
- Never cite a chunk that was not part of the recorded retrieval event.

## Implementation tasks

1. Implement a reusable embedding service with timeouts and retry limits.
2. Implement top-K pgvector similarity search.
3. Add metadata filtering and inactive-document exclusion.
4. Deduplicate overlapping results and assemble a token-bounded context.
5. Generate responses with a strict structured-output schema.
6. Validate that every citation references retrieved content.
7. Handle empty, low-score, and OpenAI/database failure paths.
8. Add retrieval fixtures and golden-question integration tests.
9. Connect successful RAG output to Feature 1's chat response.

## Acceptance criteria

- A known-answer question returns at least one valid stored chunk citation.
- Every returned citation exists in the retrieved result set.
- Inactive documents are never retrieved.
- A no-result query does not generate an unsupported factual answer.
- Retrieval latency, result IDs, scores, and model usage are recorded.
- Context length stays within a configured budget.
- Tests cover relevant results, irrelevant results, duplicate chunks, stale
  documents, and dependency failure.
- Document versions can be disabled without deleting audit history.
- Rank and chunk uniqueness constraints reject corrupt retrieval records.
- Search uses the HNSW vector index under a representative query plan.
- Stored query text and cited snapshots follow the redaction/retention policy.

## Test plan

- Clean-schema and current-schema migration tests
- Vector dimension mismatch and invalid top-K tests
- Active/inactive and document-type filter tests
- Golden questions with expected source chunks
- Empty and below-threshold retrieval tests
- Duplicate/overlapping context selection tests
- Citation order, invalid citation, and unsupported claim tests
- OpenAI timeout, database timeout, and partial processing failure tests

## Dependencies

- Feature 1 orchestrator
- Feature 2 route decision
- Existing document upload, chunking, embedding, and pgvector schema
- A small reviewed FAQ/policy evaluation set

## Out of scope

Full BM25/OpenSearch hybrid retrieval and cross-encoder reranking may be added
after the pgvector baseline is measured. PI 1 should preserve interfaces that allow
those components to be added without changing the public chat contract.

## Estimate

Large. This is the main customer-value feature in PI 1 and should receive the
largest testing allocation.
