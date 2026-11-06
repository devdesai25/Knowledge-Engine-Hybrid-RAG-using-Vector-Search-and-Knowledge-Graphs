from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from backend.app.schema.auth import UserSignup
from backend.app.database.supabase import get_db
from backend.app.services.auth_service import user_signup, login_service

router = APIRouter(tags=["auth"])

@router.post("/api/signup")
async def signup(
    user: UserSignup,
    db: AsyncSession = Depends(get_db)  
):
    return await user_signup(user, db)

@router.post("/api/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    return await login_service(form_data, db)