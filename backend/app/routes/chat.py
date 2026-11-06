from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.chat_service import retrive
from backend.app.schema.chat import ChatRequest
from backend.app.services.auth_service import get_current_user
from backend.app.database.supabase import get_db

router = APIRouter()

@router.post("/api/chat")
async def retreival(request: Request, query: ChatRequest, user_id: UUID = Depends(get_current_user), db: AsyncSession = Depends(get_db)):

    return await retrive(request ,query, user_id, db)