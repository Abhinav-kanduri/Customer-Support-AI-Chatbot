import logging

import psycopg
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.database import database_error_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/escalated", tags=["escalated"])


class EscalatedRow(BaseModel):
    order_id: str
    order_nm: str
    approved_by: str | None = None
    review_by: str | None = None
    email_status: str | None = None
    task_status: str | None = None


class EscalatedResponse(BaseModel):
    count: int
    rows: list[EscalatedRow]


def fetch_escalated_rows() -> list[EscalatedRow]:
    """Return every row from public.escalated_table."""
    with psycopg.connect(DATABASE_URL, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    order_id,
                    order_nm,
                    approved_by,
                    review_by,
                    email_status,
                    task_status
                FROM public.escalated_table
                """
            )
            records = cursor.fetchall()

    return [
        EscalatedRow(
            order_id=order_id,
            order_nm=order_nm,
            approved_by=approved_by,
            review_by=review_by,
            email_status=email_status,
            task_status=task_status,
        )
        for (
            order_id,
            order_nm,
            approved_by,
            review_by,
            email_status,
            task_status,
        ) in records
    ]


@router.get("", response_model=EscalatedResponse)
def get_escalated():
    try:
        rows = fetch_escalated_rows()
    except psycopg.OperationalError as error:
        # Connection-level problems (host unreachable, timeout, auth, etc.).
        logger.exception("Database unavailable while reading escalated_table")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "message": database_error_message(error),
                "error_type": type(error).__name__,
            },
        ) from error
    except psycopg.Error as error:
        # Any other database error (bad query, missing table, etc.).
        logger.exception("Database error while reading escalated_table")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "A database error occurred while reading escalated_table.",
                "error_type": type(error).__name__,
            },
        ) from error
    except Exception as error:
        # Catch-all so the endpoint never leaks an unhandled stack trace.
        logger.exception("Unexpected error while reading escalated_table")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred.",
                "error_type": type(error).__name__,
            },
        ) from error

    return EscalatedResponse(count=len(rows), rows=rows)
