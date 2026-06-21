CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS public.document_chunks (
    id bigserial NOT NULL,
    doc_id text NOT NULL,
    chunk_id text NOT NULL,
    chunk_text text NOT NULL,
    chunk_vector public.vector(1536) NOT NULL,
    created_timestamp timestamp with time zone DEFAULT now(),
    last_updated timestamp with time zone DEFAULT now(),
    CONSTRAINT document_chunks_pkey PRIMARY KEY (id),
    CONSTRAINT unique_doc_chunk UNIQUE (doc_id, chunk_id)
) TABLESPACE pg_default;

ALTER TABLE public.document_chunks
ALTER COLUMN chunk_vector TYPE public.vector(1536)
USING chunk_vector::public.vector(1536);

CREATE INDEX IF NOT EXISTS document_chunks_vector_hnsw_idx
ON public.document_chunks
USING hnsw (chunk_vector public.vector_cosine_ops);
