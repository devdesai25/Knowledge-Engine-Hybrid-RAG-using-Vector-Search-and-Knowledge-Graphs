import uuid
from sqlalchemy import String, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.supabase import Base

class User(Base):
    __tablename__="users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        nullable=False
    )

    password_hash: Mapped[str]= mapped_column(
        String,
        nullable=False
    )