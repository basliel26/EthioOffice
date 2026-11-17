import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class LetterAttachment(Base):
    __tablename__ = "letter_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    letter_id = Column(UUID(as_uuid=True), ForeignKey("letter_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=False, index=True)
    attached_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    attachment_type = Column(String(50), default="SUPPORTING_DOCUMENT", nullable=False)  # PRIMARY_SIGNED_PDF, SUPPORTING_DOCUMENT, ANNEX
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("letter_id", "file_id", name="uq_letter_file_attachment"),
    )

    # Relationships
    letter = relationship("LetterRegistry", back_populates="attachments")
    file_item = relationship("FileItem")
    attached_by = relationship("User")
    organization = relationship("Organization")
