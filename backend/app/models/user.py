import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Boolean, BigInteger, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"  # Platform-level administrator
    ADMIN = "ADMIN"              # Organization administrator
    MANAGER = "MANAGER"          # Department manager
    STAFF = "STAFF"              # Standard employee


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole, name="user_role_enum"), default=UserRole.STAFF, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    avatar_url = Column(String(512), nullable=True)
    storage_quota_bytes = Column(BigInteger, nullable=True)  # Null = unlimited
    used_storage_bytes = Column(BigInteger, default=0, nullable=False)
    
    # Enterprise Security: Account Lockout & Brute-Force Defense
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="users")
    departments = relationship("UserDepartment", back_populates="user", cascade="all, delete-orphan")
    owned_files = relationship("FileItem", back_populates="owner", foreign_keys="FileItem.owner_id")
    file_versions = relationship("FileVersion", back_populates="created_by")
    locks = relationship("FileLock", back_populates="locked_by")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_superuser(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN]

    @property
    def is_locked(self) -> bool:
        if self.locked_until:
            now = datetime.now(timezone.utc)
            locked_dt = self.locked_until if self.locked_until.tzinfo else self.locked_until.replace(tzinfo=timezone.utc)
            return now < locked_dt
        return False
