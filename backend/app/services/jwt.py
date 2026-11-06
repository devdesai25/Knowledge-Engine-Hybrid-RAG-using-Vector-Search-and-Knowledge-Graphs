import logging
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from pydantic import SecretStr
import anyio

from backend.app.settings import setting

logger = logging.getLogger(__name__)

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def hash_password(password: str)->str:
    return pwd_context.hash(password)

def verify(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

async def hash_password_async(password: SecretStr) -> str:
    return await anyio.to_thread.run_sync(pwd_context.hash, password.get_secret_value())

async def verify_async(plain_password: str, hashed_password: str) -> bool:
    try:
        if not plain_password or not hashed_password:
            return False
        return await anyio.to_thread.run_sync(pwd_context.verify, plain_password, hashed_password)
    except Exception as exc:
        logger.warning(f"Password verification error: {exc}")
        return False

def encode(data: dict) -> str:
    assert isinstance(data, dict)
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=setting.expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, setting.secret_key, algorithm=setting.secret_algorithm)

def decode(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, setting.secret_key, 
            algorithms=[setting.secret_algorithm]
        )
    except JWTError as exc:
        logger.debug(f"JWT decode error: {exc}")
        return None
     

oauth2scheme = OAuth2PasswordBearer(tokenUrl="/api/login")