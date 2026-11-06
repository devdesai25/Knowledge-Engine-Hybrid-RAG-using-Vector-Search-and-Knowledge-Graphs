import uuid
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.settings import setting

metadata = MetaData()
db_uri = setting.supabase_uri
if db_uri and db_uri.startswith("postgresql://"):
    db_uri = db_uri.replace("postgresql://", "postgresql+asyncpg://")

connect_args = {}
if "asyncpg" in db_uri:
    # Disable statement caching for compatibility with pgbouncer/Supabase pooler (port 6543)
    connect_args = {
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
    }

engine = create_async_engine(
    db_uri,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=240,
    connect_args=connect_args,
)

class Base(DeclarativeBase):
    pass

AsyncSessionLocal = async_sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
