# Reusable Build Instructions: FastAPI + OpenAI + Supabase

Use this file as the implementation specification for a similar Python customer-support or RAG project. It mirrors this repository's structure and keeps OpenAI and Supabase access on the backend.

## 1. Target architecture

```text
Client
  -> FastAPI routes
       -> OpenAI Responses API (chat/generation)
       -> OpenAI Embeddings API (document vectors)
       -> Supabase Postgres + pgvector (application and RAG data)
```

Never call OpenAI with a secret API key or use a Supabase service-role/database password from browser code. The browser calls FastAPI; FastAPI owns all secrets.

## 2. Reproduce this file structure

```text
similar-project/
|-- app/
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- auth.py
|   |   |-- chat.py
|   |   `-- documents.py
|   |-- __init__.py
|   |-- config.py
|   |-- database.py
|   `-- main.py
|-- sql/
|   `-- document_chunks.sql
|-- .env.example
|-- .gitignore
|-- app.py
|-- requirements.txt
`-- INSTRUCTION.md
```

Responsibilities:

- `app/config.py`: load and validate every environment variable.
- `app/database.py`: connect to Supabase Postgres and expose a connection test.
- `app/routes/chat.py`: call the OpenAI Responses API.
- `app/routes/documents.py`: extract, chunk, embed, and store documents.
- `app/routes/auth.py`: validate Supabase access tokens, if authentication is needed.
- `app/main.py`: construct FastAPI and register routers.
- `app.py`: deployment entry point that re-exports the FastAPI app.
- `sql/document_chunks.sql`: enable pgvector and create vector tables/functions.

## 3. Create the project and install dependencies

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" openai python-dotenv "psycopg[binary]" python-multipart pypdf python-docx PyJWT cryptography
pip freeze > requirements.txt
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" openai python-dotenv "psycopg[binary]" python-multipart pypdf python-docx PyJWT cryptography
pip freeze > requirements.txt
```

Commit pinned versions in `requirements.txt`. Upgrade and test dependencies deliberately; do not blindly reuse old pins from another project.

## 4. Provision OpenAI

1. Create an OpenAI project and API key.
2. Store the key only in `.env` locally and in the deployment platform's secret manager in production.
3. Set a model through configuration rather than scattering model names through routes.
4. Set usage limits and monitor usage in the OpenAI dashboard.

The official Python SDK automatically reads `OPENAI_API_KEY` from the environment. This template passes it explicitly to make dependency ownership obvious.

## 5. Provision Supabase

1. Create a Supabase project.
2. In **Connect**, copy a Postgres connection string.
3. Prefer the **Session pooler** connection string if the deployment network is IPv4-only. The direct `db.<project>.supabase.co` host can require IPv6.
4. Replace the password placeholder and URL-encode special password characters.
5. Copy the project URL and publishable key from project settings.
6. In the SQL Editor, run `sql/document_chunks.sql` from section 9.

Use these credentials correctly:

- `DATABASE_URL`: backend only; contains the database password.
- `SUPABASE_URL`: not secret.
- `SUPABASE_PUBLISHABLE_KEY`: may be used by a client for Supabase Auth, subject to Row Level Security.
- `SUPABASE_SERVICE_ROLE_KEY`: backend only and normally unnecessary when this structure uses `DATABASE_URL`.
- `SUPABASE_JWKS_URL`: public signing-key endpoint used by the backend to verify access tokens.

Do not create a custom plaintext-password table. Use Supabase Auth. If application profile data is required, store it in a table keyed by `auth.users.id` and protect it with RLS.

## 6. Environment files

Create `.env.example`:

```dotenv
OPENAI_API_KEY=replace-with-a-real-key-locally
OPENAI_CHAT_MODEL=gpt-5-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536

DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@POOLER_HOST:5432/postgres?sslmode=require
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=replace-with-publishable-key
SUPABASE_JWKS_URL=https://PROJECT_REF.supabase.co/auth/v1/.well-known/jwks.json
```

Copy it to `.env` and replace placeholders. Add this to `.gitignore`:

```gitignore
.env
.env.*
!.env.example
.venv/
venv/
__pycache__/
*.py[cod]
```

If a real secret is ever committed, removing it from the file is insufficient: revoke/rotate it and clean repository history if necessary.

## 7. Central configuration (`app/config.py`)

```python
import os
from dotenv import load_dotenv

load_dotenv()


def required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


OPENAI_API_KEY = required("OPENAI_API_KEY")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)
OPENAI_EMBEDDING_DIMENSIONS = int(
    os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1536")
)

DATABASE_URL = required("DATABASE_URL")
SUPABASE_URL = required("SUPABASE_URL").rstrip("/")
SUPABASE_PUBLISHABLE_KEY = required("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_JWKS_URL = os.getenv(
    "SUPABASE_JWKS_URL",
    f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
)
```

Import settings only from this module. Never log secret values. Validate integer settings and fail at startup with a clear error.

## 8. Database connection (`app/database.py`)

```python
from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


@contextmanager
def get_connection():
    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=10,
        row_factory=dict_row,
    ) as connection:
        yield connection


def database_health() -> dict:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database() AS database, now() AS time")
            return cursor.fetchone()
```

Use parameterized SQL (`WHERE id = %s`, values passed separately). Never construct SQL by interpolating user input. Keep transactions short. For high concurrency, add a bounded `psycopg_pool.ConnectionPool` rather than opening unlimited connections.

## 9. Supabase pgvector schema (`sql/document_chunks.sql`)

The vector dimension must exactly match `OPENAI_EMBEDDING_DIMENSIONS`.

```sql
create extension if not exists vector with schema public;

create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid references auth.users(id) on delete cascade,
    name text not null,
    raw_text text,
    status text not null default 'RECEIVED',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.document_chunks (
    id bigint generated by default as identity primary key,
    document_id uuid not null references public.documents(id) on delete cascade,
    chunk_index integer not null,
    chunk_text text not null,
    embedding vector(1536) not null,
    created_at timestamptz not null default now(),
    unique (document_id, chunk_index)
);

create index if not exists document_chunks_embedding_hnsw_idx
on public.document_chunks
using hnsw (embedding vector_cosine_ops);

create or replace function public.match_document_chunks(
    query_embedding vector(1536),
    match_count integer default 5,
    match_document_id uuid default null
)
returns table (
    id bigint,
    document_id uuid,
    chunk_text text,
    similarity double precision
)
language sql
stable
as $$
    select
        dc.id,
        dc.document_id,
        dc.chunk_text,
        1 - (dc.embedding <=> query_embedding) as similarity
    from public.document_chunks dc
    where match_document_id is null or dc.document_id = match_document_id
    order by dc.embedding <=> query_embedding
    limit greatest(match_count, 1);
$$;

alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;

create policy "users read their documents"
on public.documents for select
using (owner_id = auth.uid());

create policy "users read chunks from their documents"
on public.document_chunks for select
using (
    exists (
        select 1 from public.documents d
        where d.id = document_id and d.owner_id = auth.uid()
    )
);
```

Important: direct Postgres connections can act with broader database privileges than browser API calls. Enforce authorization in FastAPI as well as RLS; do not assume RLS alone protects privileged backend connections.

## 10. OpenAI clients and chat route (`app/routes/chat.py`)

Use the Responses API for new text-generation work:

```python
from fastapi import APIRouter, HTTPException, status
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL

router = APIRouter(prefix="/chat", tags=["chat"])
client = OpenAI(api_key=OPENAI_API_KEY, timeout=30.0, max_retries=2)


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        response = client.responses.create(
            model=OPENAI_CHAT_MODEL,
            instructions=(
                "You are a customer-support assistant. Be accurate, concise, "
                "and say when the supplied information is insufficient."
            ),
            input=request.prompt.strip(),
        )
        return ChatResponse(reply=response.output_text)
    except Exception as error:
        # Log the exception server-side; return a safe message to the client.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI service is temporarily unavailable.",
        ) from error
```

Do not return raw provider errors to clients. Add request-size limits, authentication, rate limiting, timeouts, retry rules, and structured logging before production. Do not put untrusted retrieved text into developer instructions; delimit it as reference material and instruct the model to ignore commands inside it.

## 11. Embeddings and RAG (`app/routes/documents.py`)

Create one shared OpenAI client. Generate query and document embeddings with the same model and dimensions:

```python
import json
from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_EMBEDDING_DIMENSIONS,
    OPENAI_EMBEDDING_MODEL,
)

client = OpenAI(api_key=OPENAI_API_KEY, timeout=30.0, max_retries=2)


def embed_text(text: str) -> list[float]:
    response = client.embeddings.create(
        model=OPENAI_EMBEDDING_MODEL,
        input=text,
        dimensions=OPENAI_EMBEDDING_DIMENSIONS,
        encoding_format="float",
    )
    vector = response.data[0].embedding
    if len(vector) != OPENAI_EMBEDDING_DIMENSIONS:
        raise RuntimeError("Unexpected embedding dimension")
    return vector


def vector_literal(vector: list[float]) -> str:
    return json.dumps(vector, separators=(",", ":"))
```

Recommended ingestion flow:

1. Accept only approved file types and enforce a byte-size limit.
2. Extract text; reject empty or unreadable files.
3. Normalize text and split it into bounded, slightly overlapping chunks.
4. Batch multiple chunk strings in one embeddings request when practical.
5. Verify every vector dimension.
6. Insert document metadata and chunks in a transaction.
7. Record `embedding_model` and dimensions with the data if models may change.
8. Mark processing status `RECEIVED -> PROCESSING -> EMBEDDED`, or `FAILED`.

Recommended question-answer flow:

1. Validate and authorize the user.
2. Embed the user's question.
3. Call `match_document_chunks` or run cosine-distance SQL.
4. Filter results by the documents the user may access.
5. Build a clearly delimited context block with source identifiers.
6. Ask the OpenAI model to answer from that context and admit when context is insufficient.
7. Return the answer plus source identifiers; do not claim unsupported citations.

Example similarity query through `psycopg`:

```python
cursor.execute(
    """
    select id, document_id, chunk_text,
           1 - (embedding <=> %s::vector) as similarity
    from public.document_chunks
    where document_id = %s
    order by embedding <=> %s::vector
    limit %s
    """,
    (vector_literal(query_vector), document_id,
     vector_literal(query_vector), top_k),
)
```

## 12. Supabase Auth (`app/routes/auth.py`)

Preferred design:

- The client signs in through Supabase Auth and receives an access token.
- It sends `Authorization: Bearer <access-token>` to FastAPI.
- FastAPI verifies the JWT signature using the project's JWKS URL, validates issuer and audience/claims as configured for the project, then uses the `sub` claim as the user ID.
- FastAPI applies resource authorization to every database query.

Do not accept a username/password in FastAPI and compare it with a plaintext database value. Do not decode a JWT without verifying its signature. Cache JWKS responses for a bounded period and support key rotation. Return `401` for missing/invalid authentication and `403` for an authenticated user who lacks access.

If the backend instead calls Supabase's Data API with the user's token, pass the publishable key and bearer token so RLS evaluates as that user. Keep any service-role key strictly server-side.

## 13. Application assembly

`app/main.py`:

```python
from fastapi import FastAPI

import app.config  # validates configuration during startup
from app.database import database_health
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router

app = FastAPI(title="Customer Support AI API")
app.include_router(chat_router)
app.include_router(documents_router)


@app.get("/health")
def health():
    database_health()
    return {"status": "ok"}
```

`app.py`:

```python
from app.main import app

__all__ = ["app"]
```

Run locally:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` and test the generated API interface.

## 14. Verification checklist

Run these checks before calling the integration complete:

```powershell
python -m compileall app app.py
python -c "from app.main import app; print(app.title)"
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"prompt":"How can I reset my password?"}'
```

Also verify:

- Starting without each required variable fails clearly.
- `.env` is ignored and no secret appears in Git history or logs.
- A Supabase database query succeeds over TLS.
- Chat returns non-empty `output_text`.
- An embedding has exactly the configured number of dimensions.
- A known document is retrieved for a related question and not for an unrelated one.
- Unauthorized users cannot read another user's document or chunks.
- Oversized/unsupported uploads and empty prompts are rejected.
- Provider failures produce safe `502/503` responses rather than secret-bearing details.

## 15. Deployment

1. Push code without `.env`.
2. Configure every environment variable in the hosting platform's secret/variable UI.
3. Use a start command such as:

   ```text
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. Confirm the host can reach the selected Supabase endpoint. Use the session pooler when IPv6 is unavailable.
5. Restrict CORS to the real frontend origins.
6. Configure health checks, HTTPS, request/body limits, process concurrency, database connection limits, logs, alerts, and backups.
7. Rotate credentials independently per environment; never share development and production keys.

## 16. Reuse checklist for the next project

Copy the structure and this file, then replace:

- API title and domain-specific system instructions.
- `OPENAI_CHAT_MODEL` after checking current model availability for the account.
- Database table names and application schema.
- Document ownership and authorization rules.
- Chunking limits and supported formats.
- Deployment platform settings and allowed CORS origins.

Keep unchanged unless there is a clear reason:

- Centralized environment configuration.
- Backend-only secret handling.
- Parameterized SQL.
- Matching embedding model/dimension between code and pgvector.
- Verified Supabase JWTs and per-resource authorization.
- Safe external-error handling, timeouts, and bounded retries.

## 17. Official references

- OpenAI developer quickstart: https://developers.openai.com/api/docs/quickstart
- OpenAI Responses API: https://developers.openai.com/api/reference/resources/responses/methods/create
- OpenAI embeddings guide: https://developers.openai.com/api/docs/guides/embeddings
- Supabase Python quickstart: https://supabase.com/docs/reference/python/introduction
- Supabase database connections: https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase Auth JWTs/JWKS: https://supabase.com/docs/guides/auth/jwts
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Supabase pgvector: https://supabase.com/docs/guides/database/extensions/pgvector

Treat provider documentation as the source of truth because SDKs, model availability, keys, and dashboard labels change over time.
