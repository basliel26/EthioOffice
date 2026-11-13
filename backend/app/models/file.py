import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Boolean, BigInteger, Integer, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class DriveType(str, enum.Enum):
    PERSONAL = "PERSONAL"
    COMPANY = "COMPANY"


class FileItem(Base):
    __tablename__ = "file_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(255), nullable=False, index=True)
    is_folder = Column(Boolean, default=False, nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=True, index=True)
    drive_type = Column(Enum(DriveType, name="drive_type_enum"), default=DriveType.PERSONAL, nullable=False, index=True)
    
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    
    mime_type = Column(String(120), nullable=True)
    size_bytes = Column(BigInteger, default=0, nullable=False)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="file_items")
    owner = relationship("User", back_populates="owned_files", foreign_keys=[owner_id])
    department = relationship("Department", back_populates="company_drive_roots")
    parent = relationship("FileItem", remote_side=[id], back_populates="children")
    children = relationship("FileItem", back_populates="parent", cascade="all, delete-orphan")
    versions = relationship("FileVersion", back_populates="file_item", cascade="all, delete-orphan", order_by="desc(FileVersion.version_number)")
    shares = relationship("FileShare", back_populates="file_item", cascade="all, delete-orphan")
    lock = relationship("FileLock", back_populates="file_item", uselist=False, cascade="all, delete-orphan")
    eurooffice_sessions = relationship("EuroOfficeSession", back_populates="file_item", cascade="all, delete-orphan")
    search_index = relationship("FileSearchIndex", back_populates="file_item", uselist=False, cascade="all, delete-orphan")
    tags = relationship("FileTag", back_populates="file_item", cascade="all, delete-orphan")

    @property
    def current_version(self):
        if not self.versions:
            return None
        for v in self.versions:
            if v.id == self.current_version_id:
                return v
        return self.versions[0]


class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    storage_path = Column(String(512), nullable=False)
    checksum_sha256 = Column(String(64), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_summary = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("file_id", "version_number", name="uq_file_version_number"),
    )

    # Relationships
    file_item = relationship("FileItem", back_populates="versions")
    created_by = relationship("User", back_populates="file_versions")
