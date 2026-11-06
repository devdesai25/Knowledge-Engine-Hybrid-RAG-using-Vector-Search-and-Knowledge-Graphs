from uuid import UUID

from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schema.auth import UserSignup
from backend.app.models.user import User
from backend.app.services.jwt import hash_password_async, encode, verify_async, oauth2scheme, decode
from backend.app.database.supabase import get_db

async def user_signup(
    user: UserSignup, 
    db: AsyncSession
):
    print(user)
    stmt = select(User).where((User.email == user.email))
    existing_user = (await db.execute(stmt)).scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )
    hashed = await hash_password_async(user.password)

    new_user = User(
        email=user.email,
        password_hash=hashed
    )
    try:
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
    except Exception as exc:
        await db.rollback()
        raise 

    access_token = encode({
        "sub": str(new_user.id),
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user":{
            "id": new_user.id
        }
    }

async def login_service(
    form_data: OAuth2PasswordRequestForm,
    db: AsyncSession
) -> dict:

    if not form_data or not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=401,
            detail="Iklwgnoinvalid Password or Email"
        )

    existing_user = (
        await db.execute(
            select(User).where(User.email == form_data.username)
        )
    ).scalar_one_or_none()

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid Password or Email"
        )

    is_valid = await verify_async(form_data.password, existing_user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid Password or Email"
        )
    access_token = encode({
        "sub": str(existing_user.id)
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

async def get_current_user(
    token: str = Depends(oauth2scheme),
    db: AsyncSession = Depends(get_db)
):
    payload = decode(token)

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Token invalid"
        )

    sub = payload.get('sub')

    if not sub:
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(sub)

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid token payload",
        )  
    return user_id