# Feature 3: Document Ingestion and Vector Embeddings

## Status

Built as a document ingestion and RAG-preparation pipeline.

## What is implemented

The backend can accept support documents, extract their text, split that text into
chunks, create OpenAI embeddings, and save the vectors in PostgreSQL/Supabase with
pgvector.

### Upload documents

`POST /documents/upload`

- Accepts PDF, DOCX, and TXT files.
- Rejects unsupported or empty files.
- Extracts readable text from the uploaded file.
- Creates a document ID and saves the source text in `public.documents`.
- Starts the document with the `RECEIVED` status.

### Process a complete document

`POST /documents/{doc_id}/process`

- Loads the uploaded document from the database.
- Moves through `PROCESSING`, `CHUNKED`, and `EMBEDDED` statuses.
- Splits text into chunks of up to 1,500 characters.
- Creates a 1,536-dimension embedding for every chunk with
  `text-embedding-3-small`.
- Saves chunks and vectors in `public.document_chunks`.
- Marks processing errors with the `FAILED` status.

### Store one paragraph

`POST /documents/chunks`

- Accepts a single paragraph.
- Generates missing document and chunk IDs.
- Creates an embedding and inserts or updates the matching vector record.

## Main source files

- `app/routes/documents.py`
- `sql/document_chunks.sql`

The SQL file enables pgvector, creates the `document_chunks` table, and creates an
HNSW vector index.

## Required services

- OpenAI API access through `OPENAI_API_KEY`
- PostgreSQL/Supabase through `DATABASE_URL`
- A database containing the `documents` and `document_chunks` structures expected
  by the routes

## How to verify

Run the backend and use the document endpoints in
`http://127.0.0.1:8000/docs`. Upload a file first, copy its `doc_id`, and then call
the processing endpoint with that ID.

## Current limitations

- Vector creation and storage are implemented, but a vector-search endpoint is not
  present in the current route code.
- The `/chat` endpoint is not yet connected to these stored chunks.
- Processing runs synchronously, so large documents may take a long time.
- Reprocessing a document creates new random chunk IDs rather than replacing a
  stable set of chunks.

