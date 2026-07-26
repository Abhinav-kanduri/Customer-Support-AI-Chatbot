BEGIN;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS public.documents (
    doc_id text PRIMARY KEY,
    doc_nm text NOT NULL,
    doc_type text NOT NULL,
    doc_raw_text text,
    doc_status text NOT NULL DEFAULT 'RECEIVED',
    document_version text NOT NULL DEFAULT '1',
    mime_type text,
    source_uri text,
    checksum_sha256 text,
    is_active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by uuid REFERENCES public.support_users(user_id) ON DELETE SET NULL,
    create_timestamp timestamptz NOT NULL DEFAULT now(),
    last_update_timestamp timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.documents
    ADD COLUMN IF NOT EXISTS document_version text NOT NULL DEFAULT '1',
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS source_uri text,
    ADD COLUMN IF NOT EXISTS checksum_sha256 text,
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_by uuid;

CREATE INDEX IF NOT EXISTS idx_documents_type_active
    ON public.documents (doc_type, is_active);
CREATE INDEX IF NOT EXISTS idx_documents_status_updated
    ON public.documents (doc_status, last_update_timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_checksum_version
    ON public.documents (checksum_sha256, document_version)
    WHERE checksum_sha256 IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.document_chunks (
    id bigserial PRIMARY KEY,
    doc_id text NOT NULL,
    chunk_id text NOT NULL,
    chunk_text text NOT NULL,
    chunk_vector vector(1536) NOT NULL,
    created_timestamp timestamptz NOT NULL DEFAULT now(),
    last_updated timestamptz NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_id)
);

ALTER TABLE public.document_chunks
    ADD COLUMN IF NOT EXISTS chunk_index integer,
    ADD COLUMN IF NOT EXISTS page_number integer,
    ADD COLUMN IF NOT EXISTS section_title text,
    ADD COLUMN IF NOT EXISTS token_count integer,
    ADD COLUMN IF NOT EXISTS embedding_model text
        NOT NULL DEFAULT 'text-embedding-3-small',
    ADD COLUMN IF NOT EXISTS embedding_dimensions integer NOT NULL DEFAULT 1536,
    ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS document_chunks_vector_hnsw_idx
    ON public.document_chunks
    USING hnsw (chunk_vector vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_document_chunks_doc_active_index
    ON public.document_chunks (doc_id, is_active, chunk_index);
CREATE INDEX IF NOT EXISTS idx_document_chunks_metadata_gin
    ON public.document_chunks USING gin (metadata);

CREATE TABLE IF NOT EXISTS public.retrieval_events (
    retrieval_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id uuid NOT NULL
        REFERENCES public.pipeline_runs(run_id) ON DELETE CASCADE,
    query_message_id uuid NOT NULL
        REFERENCES public.messages(message_id) ON DELETE CASCADE,
    query_redacted text NOT NULL,
    embedding_model text NOT NULL,
    top_k integer NOT NULL CHECK (top_k BETWEEN 1 AND 50),
    minimum_similarity numeric(7,6) NOT NULL
        CHECK (minimum_similarity BETWEEN 0 AND 1),
    applied_filters jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(applied_filters) = 'object'),
    result_count integer NOT NULL DEFAULT 0 CHECK (result_count >= 0),
    retrieval_status text NOT NULL
        CHECK (retrieval_status IN ('started', 'completed', 'empty', 'failed')),
    retrieval_latency_ms integer
        CHECK (retrieval_latency_ms IS NULL OR retrieval_latency_ms >= 0),
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_retrieval_events_run
    ON public.retrieval_events (run_id, created_at);
CREATE INDEX IF NOT EXISTS idx_retrieval_events_status_created
    ON public.retrieval_events (retrieval_status, created_at DESC);

CREATE TABLE IF NOT EXISTS public.retrieval_results (
    retrieval_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    retrieval_event_id uuid NOT NULL
        REFERENCES public.retrieval_events(retrieval_event_id) ON DELETE CASCADE,
    document_chunk_id bigint NOT NULL
        REFERENCES public.document_chunks(id) ON DELETE RESTRICT,
    result_rank integer NOT NULL CHECK (result_rank > 0),
    similarity_score numeric(7,6) NOT NULL
        CHECK (similarity_score BETWEEN -1 AND 1),
    selected_for_context boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (retrieval_event_id, result_rank),
    UNIQUE (retrieval_event_id, document_chunk_id)
);

CREATE INDEX IF NOT EXISTS idx_retrieval_results_chunk
    ON public.retrieval_results (document_chunk_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.response_citations (
    citation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    assistant_message_id uuid NOT NULL
        REFERENCES public.messages(message_id) ON DELETE CASCADE,
    retrieval_result_id uuid NOT NULL
        REFERENCES public.retrieval_results(retrieval_result_id) ON DELETE RESTRICT,
    citation_order integer NOT NULL CHECK (citation_order > 0),
    cited_text_snapshot text,
    validation_status text NOT NULL DEFAULT 'pending'
        CHECK (validation_status IN ('pending', 'valid', 'invalid', 'unsupported')),
    validation_detail_safe text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (assistant_message_id, citation_order),
    UNIQUE (assistant_message_id, retrieval_result_id)
);

CREATE INDEX IF NOT EXISTS idx_response_citations_validation
    ON public.response_citations (validation_status, created_at DESC);

CREATE OR REPLACE FUNCTION public.match_document_chunks(
    p_query_embedding vector(1536),
    p_result_limit integer DEFAULT 5,
    p_minimum_similarity double precision DEFAULT 0.0,
    p_doc_type text DEFAULT NULL
)
RETURNS TABLE (
    document_chunk_id bigint,
    doc_id text,
    chunk_id text,
    doc_nm text,
    doc_type text,
    chunk_text text,
    page_number integer,
    section_title text,
    similarity_score double precision
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        dc.id,
        dc.doc_id,
        dc.chunk_id,
        d.doc_nm,
        d.doc_type,
        dc.chunk_text,
        dc.page_number,
        dc.section_title,
        1 - (dc.chunk_vector <=> p_query_embedding) AS similarity_score
    FROM public.document_chunks AS dc
    JOIN public.documents AS d
      ON d.doc_id = dc.doc_id
    WHERE d.is_active
      AND dc.is_active
      AND d.doc_status = 'EMBEDDED'
      AND (p_doc_type IS NULL OR d.doc_type = p_doc_type)
      AND 1 - (dc.chunk_vector <=> p_query_embedding) >= p_minimum_similarity
    ORDER BY dc.chunk_vector <=> p_query_embedding
    LIMIT LEAST(GREATEST(p_result_limit, 1), 50);
$$;

COMMIT;
