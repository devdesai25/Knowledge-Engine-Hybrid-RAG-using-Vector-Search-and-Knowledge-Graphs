import uuid

from sqlalchemy import UUID, ForeignKey, Text, Integer, DateTime, Index, Computed
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TSVECTOR

from backend.app.database.supabase import Base

class Chunk(Base):
    __tablename__="chunks"

    chunk_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        default=uuid.uuid4,
        primary_key=True
    )
    doc_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.doc_id"),
        nullable=False
    )
    user_id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    fts : Mapped[TSVECTOR] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', content)",
            persisted=True
        ),
        nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    #token_count: Mapped[int] = mapped_column(Integer,nullable=False)

    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_name: Mapped[str | None] = mapped_column(Text, nullable=False)
    heading: Mapped[str | None] = mapped_column(Text, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    document = relationship(
        "Document",
        back_populates="chunks"
    )

    __table_args__ = (
        Index("chunks_ftx_idx", "fts", postgresql_using="gin"),
        Index("chunks_doc_chunk_idx", "doc_id", "chunk_id")
    )
    