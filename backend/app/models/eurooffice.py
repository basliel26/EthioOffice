import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class EuroOfficeSession(Base):
    __tablename__ = "eurooffice_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_key = Column(String(128), unique=True, nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=False, index=True)
    active_users = Column(JSONB, default=list, nullable=False)
    is_editing = Column(Boolean, default=True, nullable=False)
    last_saved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    file_item = relationship("FileItem", back_populates="eurooffice_sessions")
