from fastapi import FastAPI
import time

app = FastAPI(title="Customer Support AI Chatbot")

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
