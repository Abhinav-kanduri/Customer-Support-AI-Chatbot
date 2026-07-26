# PI-1 Database DDL

These PostgreSQL migration drafts support the five PI-1 feature specifications.
They are planning artifacts and have not been applied to any environment.

## Execution order

1. `001_conversation_orchestrator.sql`
2. `002_nlu_routing.sql`
3. `003_rag_retrieval.sql`
4. `004_guardrails_escalation.sql`
5. `005_feedback_observability.sql`

The order matters because later migrations reference tables created by earlier
migrations.

## Compatibility notes

- The scripts target PostgreSQL with `pgcrypto`; Feature 3 also requires pgvector.
- IDs for new operational records use native UUID values.
- `documents.doc_id` and `document_chunks.doc_id/chunk_id` remain text to preserve
  compatibility with the current API-generated `doc_...` and `chunk_...` values.
- Feature 3 uses additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` statements for
  existing document tables.
- Existing environments must be inspected and backed up before these drafts are
  promoted into production migrations.
- `CREATE TABLE IF NOT EXISTS` does not reconcile incompatible existing columns.
  A schema diff and data backfill are required before adding stricter constraints.
- Destructive rollback statements are intentionally not included.

## Migration rules

- Apply each migration in a transaction in a controlled environment.
- Record applied versions in a migration-history table or migration framework.
- Test both a clean database and a copy of the current development schema.
- Backfill required relationships before adding foreign keys.
- Do not store raw secrets, payment-card values, or unmasked PII in telemetry.
- Use a restricted application role instead of a database-owner connection.
- Add Supabase row-level security policies when direct client access is introduced.

