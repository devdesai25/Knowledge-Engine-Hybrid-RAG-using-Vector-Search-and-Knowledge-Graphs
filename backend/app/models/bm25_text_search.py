import uuid

from sqlalchemy import String, UUID, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.app.database.supabase import Base

class Document(Base):
    __tablename__="documents"

    doc_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    
    doc_name : Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    created_at : Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    chunks = relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan"
    )