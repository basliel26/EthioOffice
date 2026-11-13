import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(20), default="#3b82f6", nullable=False)  # Hex color
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_tag_name"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="tags")
    file_associations = relationship("FileTag", back_populates="tag", cascade="all, delete-orphan")


class FileTag(Base):
    __tablename__ = "file_tags"

    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=False)
    tag_id = Column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    assigned_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("file_id", "tag_id"),
    )

    # Relationships
    file_item = relationship("FileItem", back_populates="tags")
    tag = relationship("Tag", back_populates="file_associations")
    assigned_by = relationship("User")
