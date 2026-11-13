import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, PrimaryKeyConstraint, UniqueConstraint, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True, index=True)
    
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False)  # e.g., 'HR', 'FIN'
    description = Column(Text, nullable=True)
    
    storage_quota_bytes = Column(BigInteger, nullable=True)  # Null = unlimited / inherits org quota
    used_storage_bytes = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_org_dept_name"),
        UniqueConstraint("organization_id", "code", name="uq_org_dept_code"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="departments")
    parent = relationship("Department", remote_side=[id], back_populates="children")
    children = relationship("Department", back_populates="parent", cascade="all, delete-orphan")
    members = relationship("UserDepartment", back_populates="department", cascade="all, delete-orphan")
    company_drive_roots = relationship("FileItem", back_populates="department")


class UserDepartment(Base):
    __tablename__ = "user_departments"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    is_department_lead = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "department_id"),
    )

    # Relationships
    user = relationship("User", back_populates="departments")
    department = relationship("Department", back_populates="members")
