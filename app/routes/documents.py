import io
import json
import logging
import os
from uuid import uuid4

import psycopg
import pypdf
from docx import Document as DocxDocument
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class DocumentChunkRequest(BaseModel):
    paragraph: str = Field(min_length=1)
    doc_id: str | None = None
    chunk_id: str | None = None


class DocumentChunkResponse(BaseModel):
    id: int
    doc_id: str
    chunk_id: str
    chunk_text: str
    embedding_model: str
    embedding_dimensions: int
    created_timestamp: str
    last_updated: str


@router.post(
    "/chunks",
    response_model=DocumentChunkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_chunk(
    request: DocumentChunkRequest,
) -> DocumentChunkResponse:
    chunk_text = request.paragraph.strip()
    if not chunk_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="paragraph must contain non-whitespace text",
        )

    doc_id = request.doc_id or f"doc_{uuid4().hex}"
    chunk_id = request.chunk_id or f"chunk_{uuid4().hex}"

    try:
        embedding_response = OpenAI().embeddings.create(
            model=EMBEDDING_MODEL,
            input=chunk_text,
            dimensions=EMBEDDING_DIMENSIONS,
            encoding_format="float",
        )
        embedding = embedding_response.data[0].embedding
    except Exception as error:
        logger.exception("Failed to create an embedding")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI embedding generation failed",
        ) from error

    if len(embedding) != EMBEDDING_DIMENSIONS:
        logger.error(
            "Unexpected embedding size: expected %s, received %s",
            EMBEDDING_DIMENSIONS,
            len(embedding),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI returned an unexpected embedding size",
        )

    vector_value = json.dumps(embedding, separators=(",", ":"))

    try:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.document_chunks (
                        doc_id,
                        chunk_id,
                        chunk_text,
                        chunk_vector
                    )
                    VALUES (%s, %s, %s, %s::public.vector)
                    ON CONFLICT (doc_id, chunk_id)
                    DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        chunk_vector = EXCLUDED.chunk_vector,
                        last_updated = now()
                    RETURNING
                        id,
                        doc_id,
                        chunk_id,
                        chunk_text,
                        created_timestamp,
                        last_updated
                    """,
                    (doc_id, chunk_id, chunk_text, vector_value),
                )
                row = cursor.fetchone()
    except Exception as error:
        logger.exception("Failed to save the document chunk")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document chunk could not be saved",
        ) from error

    return DocumentChunkResponse(
        id=row[0],
        doc_id=row[1],
        chunk_id=row[2],
        chunk_text=row[3],
        embedding_model=EMBEDDING_MODEL,
        embedding_dimensions=EMBEDDING_DIMENSIONS,
        created_timestamp=row[4].isoformat(),
        last_updated=row[5].isoformat(),
    )


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class DocumentUploadResponse(BaseModel):
    doc_id: str
    doc_nm: str
    doc_type: str
    doc_status: str
    char_count: int
    create_timestamp: str
    last_update_timestamp: str


def _extract_text(filename: str, content: bytes) -> str:
    ext = os.path.splitext(filename.lower())[1]

    if ext == ".pdf":
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(
            page.extract_text() or "" for page in reader.pages
        ).strip()

    if ext == ".docx":
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs).strip()

    if ext == ".txt":
        return content.decode("utf-8", errors="replace").strip()

    raise ValueError(f"Unsupported file type: {ext}")


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )

    try:
        raw_text = _extract_text(file.filename, content)
    except Exception as error:
        logger.exception("Failed to parse document: %s", file.filename)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not extract text from file: {error}",
        ) from error

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from the uploaded file",
        )

    doc_id = f"doc_{uuid4().hex}"
    doc_type = ext.lstrip(".")

    try:
        with psycopg.connect(DATABASE_URL) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.documents (
                        doc_id,
                        doc_nm,
                        doc_type,
                        doc_raw_text,
                        doc_status
                    )
                    VALUES (%s, %s, %s, %s, 'RECEIVED')
                    RETURNING
                        doc_id,
                        doc_nm,
                        doc_type,
                        doc_status,
                        create_timestamp,
                        last_update_timestamp
                    """,
                    (doc_id, file.filename, doc_type, raw_text),
                )
                row = cursor.fetchone()
    except Exception as error:
        logger.exception("Failed to insert document record")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document record could not be saved",
        ) from error

    return DocumentUploadResponse(
        doc_id=row[0],
        doc_nm=row[1],
        doc_type=row[2],
        doc_status=row[3],
        char_count=len(raw_text),
        create_timestamp=row[4].isoformat(),
        last_update_timestamp=row[5].isoformat(),
    )


# ---------------------------------------------------------------------------
# Document processing: RECEIVED → PROCESSING → CHUNKED → EMBEDDED / FAILED
# ---------------------------------------------------------------------------

MAX_CHUNK_CHARS = 1500


class ProcessDocumentResponse(BaseModel):
    doc_id: str
    doc_nm: str
    doc_status: str
    chunks_processed: int


def _set_doc_status(doc_id: str, doc_nm: str, new_status: str) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE public.documents
                SET doc_status = %s, last_update_timestamp = now()
                WHERE doc_id = %s
                """,
                (new_status, doc_id),
            )
    logger.info("[%s] %r  ──►  %s", doc_id, doc_nm, new_status)


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]

    chunks: list[str] = []
    buffer: list[str] = []
    buffer_len = 0

    for para in paragraphs:
        # Para itself exceeds max_chars — flush buffer first, then slice it
        if len(para) > max_chars:
            if buffer:
                chunks.append("\n\n".join(buffer))
                buffer, buffer_len = [], 0
            for i in range(0, len(para), max_chars):
                piece = para[i : i + max_chars].strip()
                if piece:
                    chunks.append(piece)
            continue

        # Adding this para would overflow the buffer — flush first
        joined_len = buffer_len + (2 if buffer else 0) + len(para)
        if buffer and joined_len > max_chars:
            chunks.append("\n\n".join(buffer))
            buffer, buffer_len = [], 0

        buffer.append(para)
        buffer_len += (2 if len(buffer) > 1 else 0) + len(para)

    if buffer:
        chunks.append("\n\n".join(buffer))

    return chunks


@router.post(
    "/{doc_id}/process",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_200_OK,
)
def process_document(doc_id: str) -> ProcessDocumentResponse:
    # ── 1. Fetch document ────────────────────────────────────────────────────
    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT doc_id, doc_nm, doc_type, doc_raw_text, doc_status
                    FROM public.documents
                    WHERE doc_id = %s
                    """,
                    (doc_id,),
                )
                row = cur.fetchone()
    except Exception as error:
        logger.exception("DB error while fetching doc_id=%s", doc_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error while fetching document",
        ) from error

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found",
        )

    _, doc_nm, _, doc_raw_text, current_status = row
    logger.info("[%s] %r  found  (current status: %s)", doc_id, doc_nm, current_status)

    embedded_chunks: list[tuple[str, str, str, str]] = []

    try:
        # ── 2. PROCESSING ────────────────────────────────────────────────────
        _set_doc_status(doc_id, doc_nm, "PROCESSING")

        # ── 3. Split into chunks ─────────────────────────────────────────────
        chunks = _chunk_text(doc_raw_text)
        logger.info("[%s] %r  split into %d chunk(s)", doc_id, doc_nm, len(chunks))

        # ── 4. CHUNKED ───────────────────────────────────────────────────────
        _set_doc_status(doc_id, doc_nm, "CHUNKED")

        # ── 5. Embed each chunk ──────────────────────────────────────────────
        openai_client = OpenAI()
        for i, chunk_text in enumerate(chunks, start=1):
            logger.info(
                "[%s] embedding chunk %d/%d  (%d chars)",
                doc_id, i, len(chunks), len(chunk_text),
            )
            embedding_response = openai_client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=chunk_text,
                dimensions=EMBEDDING_DIMENSIONS,
                encoding_format="float",
            )
            embedding = embedding_response.data[0].embedding
            embedded_chunks.append((
                doc_id,
                f"chunk_{uuid4().hex}",
                chunk_text,
                json.dumps(embedding, separators=(",", ":")),
            ))

        # ── 6. Bulk-insert chunks ─────────────────────────────────────────────
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                for chunk_doc_id, chunk_id, chunk_text, vector_value in embedded_chunks:
                    cur.execute(
                        """
                        INSERT INTO public.document_chunks (
                            doc_id, chunk_id, chunk_text, chunk_vector
                        )
                        VALUES (%s, %s, %s, %s::public.vector)
                        ON CONFLICT (doc_id, chunk_id) DO UPDATE SET
                            chunk_text    = EXCLUDED.chunk_text,
                            chunk_vector  = EXCLUDED.chunk_vector,
                            last_updated  = now()
                        """,
                        (chunk_doc_id, chunk_id, chunk_text, vector_value),
                    )
        logger.info(
            "[%s] %r  inserted %d chunk(s) into document_chunks",
            doc_id, doc_nm, len(embedded_chunks),
        )

        # ── 7. EMBEDDED ───────────────────────────────────────────────────────
        _set_doc_status(doc_id, doc_nm, "EMBEDDED")

    except HTTPException:
        raise
    except Exception as error:
        logger.exception("[%s] %r  processing failed", doc_id, doc_nm)
        try:
            _set_doc_status(doc_id, doc_nm, "FAILED")
        except Exception:
            logger.exception("[%s] could not update status to FAILED", doc_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed",
        ) from error

    return ProcessDocumentResponse(
        doc_id=doc_id,
        doc_nm=doc_nm,
        doc_status="EMBEDDED",
        chunks_processed=len(embedded_chunks),
    )
