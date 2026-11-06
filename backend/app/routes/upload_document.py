from uuid import UUID
from fastapi import File, APIRouter, UploadFile, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.upload_service import upload_service
from backend.app.services.auth_service import get_current_user
from backend.app.database.supabase import get_db

router = APIRouter(tags=["Multiple file upload"])

@router.post("/api/upload")
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    user_id: UUID = Depends(get_current_user),
):  
    return await upload_service(request, files, user_id)
