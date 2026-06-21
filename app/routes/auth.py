import logging

import psycopg
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.config import DATABASE_URL
from app.database import database_error_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str  # "YES" if credentials match, otherwise "NO"
    user_role: str | None = None  # mapped from app_users when credentials match


def verify_credentials(username: str, password: str) -> str | None:
    """Return the user's role if username/password match, otherwise None."""
    with psycopg.connect(DATABASE_URL, connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT password, user_role
                FROM public.app_users
                WHERE username = %s
                """,
                (username,),
            )
            row = cursor.fetchone()

    # No such user.
    if row is None:
        return None

    stored_password, user_role = row
    if stored_password != password:
        return None

    return user_role


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest):
    # Reject empty input before touching the database.
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username and password are required",
        )

    try:
        user_role = verify_credentials(request.username, request.password)
    except psycopg.OperationalError as error:
        # Connection-level problems (host unreachable, timeout, auth, etc.).
        logger.exception("Database unavailable during login")
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
        logger.exception("Database error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "A database error occurred while verifying credentials.",
                "error_type": type(error).__name__,
            },
        ) from error
    except Exception as error:
        # Catch-all so the endpoint never leaks an unhandled stack trace.
        logger.exception("Unexpected error during login")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "message": "An unexpected error occurred.",
                "error_type": type(error).__name__,
            },
        ) from error

    if user_role is None:
        return LoginResponse(message="NO", user_role=None)

    return LoginResponse(message="YES", user_role=user_role)
