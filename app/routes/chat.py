from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from app.config import OPENAI_API_KEY

router = APIRouter(prefix="/chat", tags=["chat"])

client = OpenAI(api_key=OPENAI_API_KEY)


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    reply: str


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful customer support assistant. "
                        "Answer clearly and concisely."
                    ),
                },
                {"role": "user", "content": request.prompt},
            ],
        )
        return ChatResponse(reply=completion.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
