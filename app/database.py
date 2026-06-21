import logging
import socket

import psycopg
from fastapi import APIRouter, HTTPException, status

from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/database", tags=["database"])


def test_database_connection() -> dict[str, str]:
    with psycopg.connect(DATABASE_URL, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    current_user,
                    current_setting('server_version')
                """
            )
            database, user, server_version = cursor.fetchone()

    return {
        "status": "connected",
        "database": database,
        "user": user,
        "server_version": server_version,
    }


def check_database_connection() -> bool:
    return test_database_connection()["status"] == "connected"


def database_error_message(error: Exception) -> str:
    database_url = DATABASE_URL
    error_text = str(error).lower()

    if (
        "failed to resolve host" in error_text
        or isinstance(error.__cause__, socket.gaierror)
    ):
        if "db." in database_url and ".supabase.co" in database_url:
            return (
                "The Supabase direct database host requires IPv6, but this "
                "network is IPv4-only. In Supabase, open Connect, select "
                "Session pooler, and use that connection string as DATABASE_URL."
            )
        return "The database hostname could not be resolved."

    return "Database connection failed. Check DATABASE_URL and network access."


@router.get("/test")
def test_connection():
    try:
        return test_database_connection()
    except Exception as error:
        logger.exception("Database connection test failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "message": database_error_message(error),
                "error_type": type(error).__name__,
            },
        ) from error
