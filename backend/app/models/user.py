import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Boolean, BigInteger, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    STAFF = "STAFF"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role_enum"), default=UserRole.STAFF, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    avatar_url = Column(String(512), nullable=True)
    storage_quota_bytes = Column(BigInteger, nullable=True)  # Null = unlimited
    used_storage_bytes = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    departments = relationship("UserDepartment", back_populates="user", cascade="all, delete-orphan")
    owned_files = relationship("FileItem", back_populates="owner", foreign_keys="FileItem.owner_id")
    file_versions = relationship("FileVersion", back_populates="created_by")
    locks = relationship("FileLock", back_populates="locked_by")
