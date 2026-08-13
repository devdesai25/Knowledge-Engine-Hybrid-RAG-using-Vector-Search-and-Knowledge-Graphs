from fastapi import File, APIRouter, UploadFile

from backend.app.services.upload_service import upload_service

router = APIRouter(tags=["Multiple file upload"])

@router.post("/upload")
async def upload_documents(
    files: list[UploadFile] = File(...)
):  
    print("HERE")
    return await upload_service(files)