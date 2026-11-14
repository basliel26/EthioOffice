from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from sqlalchemy.orm import relationship
from app.core.database import Base


class SearchIndexStatus(str, enum.Enum):
    PENDING = "PENDING"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class FileSearchIndex(Base):
    __tablename__ = "file_search_index"

    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), primary_key=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name = Column(String(255), nullable=True, index=True)

    extracted_text = Column(Text, nullable=True)
    normalized_text = Column(Text, nullable=True)
    search_vector = Column(TSVECTOR, nullable=False)

    content_hash = Column(String(64), nullable=True)  # SHA-256 fingerprint
    status = Column(String(20), default=SearchIndexStatus.INDEXED.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    character_count = Column(Integer, default=0, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)

    indexed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_file_search_vector", "search_vector", postgresql_using="gin"),
    )

    # Relationships
    file_item = relationship("FileItem", back_populates="search_index")
    organization = relationship("Organization")
