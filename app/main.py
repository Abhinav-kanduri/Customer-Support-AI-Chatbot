import time

from fastapi import FastAPI

# Importing config loads the .env file, validates required variables, and
# configures logging (so this must come before the other app imports).
import app.config  # noqa: F401

from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.auth import router as auth_router
from app.routes.escalated import router as escalated_router
from app.database import check_database_connection, router as database_router

app = FastAPI(title="Customer Support AI Chatbot")
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(auth_router)
app.include_router(escalated_router)
app.include_router(database_router)

START_TIME = time.time()


@app.get("/health")
def health():
    try:
        database_status = (
            "connected" if check_database_connection() else "unavailable"
        )
    except Exception:
        database_status = "unavailable"

    return {
        "status": "ok",
        "database": database_status,
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@app.get("/")
def root():
    return {"message": "Customer Support AI Chatbot is running"}
