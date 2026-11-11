from datetime import datetime, timezone
from sqlalchemy import Column, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship
from app.core.database import Base


class FileSearchIndex(Base):
    __tablename__ = "file_search_index"

    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), primary_key=True)
    extracted_text = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=False)
    indexed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_file_search_vector", "search_vector", postgresql_using="gin"),
    )

    # Relationships
    file_item = relationship("FileItem", back_populates="search_index")
