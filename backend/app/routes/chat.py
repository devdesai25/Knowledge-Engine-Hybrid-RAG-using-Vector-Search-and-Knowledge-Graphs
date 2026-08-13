from fastapi import APIRouter
from pydantic import BaseModel

from backend.app.services.chat_service import retrive
from backend.app.schema.chat import ChatRequest

router = APIRouter()

@router.post("/chat")
async def retreival(query: ChatRequest):

    return await retrive(query)