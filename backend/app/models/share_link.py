import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class LinkAccessType(str, enum.Enum):
    VIEW_ONLY = "VIEW_ONLY"
    ALLOW_DOWNLOAD = "ALLOW_DOWNLOAD"
    UPLOAD_DROPBOX = "UPLOAD_DROPBOX"  # Allows external users to upload files to this folder


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    token = Column(String(128), unique=True, nullable=False, index=True)  # Secure random URL token
    password_hash = Column(String(255), nullable=True)                    # Optional password protection
    access_type = Column(Enum(LinkAccessType, name="link_access_type_enum"), default=LinkAccessType.ALLOW_DOWNLOAD, nullable=False)
    
    expires_at = Column(DateTime(timezone=True), nullable=True)
    max_downloads = Column(Integer, nullable=True)                        # Null = unlimited
    download_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    file_item = relationship("FileItem")
    created_by = relationship("User")
