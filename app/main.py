from fastapi import FastAPI
import time
from dotenv import load_dotenv
from app.routes.chat import router as chat_router

load_dotenv()

app = FastAPI(title="Customer Support AI Chatbot")
app.include_router(chat_router)

START_TIME = time.time()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }


@app.get("/")
def root():
    return {"message": "Customer Support AI Chatbot is running"}
