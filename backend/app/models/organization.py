import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Boolean, BigInteger, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class LicenseTier(str, enum.Enum):
    STARTER = "STARTER"
    BUSINESS = "BUSINESS"
    ENTERPRISE = "ENTERPRISE"


class OrganizationStatus(str, enum.Enum):
    TRIAL = "TRIAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)  # e.g., 'cbe-bank', 'awash-corp'
    tin_number = Column(String(50), nullable=True, index=True)  # Ethiopian Tax Identification Number
    logo_url = Column(String(512), nullable=True)
    theme_color = Column(String(20), default="#059669", nullable=False)  # Primary branding hex color
    
    status = Column(Enum(OrganizationStatus, name="org_status_enum"), default=OrganizationStatus.ACTIVE, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    max_users = Column(Integer, default=50, nullable=False)
    storage_limit_bytes = Column(BigInteger, default=100 * 1024 * 1024 * 1024, nullable=False)  # Default 100 GB
    used_storage_bytes = Column(BigInteger, default=0, nullable=False)
    
    # Enterprise Security: IP Whitelisting / Corporate LAN & VPN Subnet Fencing
    allowed_ip_ranges = Column(String(512), nullable=True)  # Comma-separated CIDRs e.g. "10.0.0.0/8, 192.168.1.0/24"
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan", foreign_keys="User.organization_id")
    departments = relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    file_items = relationship("FileItem", back_populates="organization", cascade="all, delete-orphan")
    license = relationship("License", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    license_history = relationship("LicenseHistory", back_populates="organization", cascade="all, delete-orphan", order_by="desc(LicenseHistory.activated_at)")
    letter_records = relationship("LetterRegistry", back_populates="organization", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="organization", cascade="all, delete-orphan")


class License(Base):
    __tablename__ = "licenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    license_key = Column(String(2048), unique=True, nullable=False, index=True)
    tier = Column(Enum(LicenseTier, name="license_tier_enum"), default=LicenseTier.BUSINESS, nullable=False)
    
    max_users = Column(Integer, nullable=False)
    storage_limit_bytes = Column(BigInteger, nullable=False)
    features = Column(String(1024), nullable=True)  # Comma-separated list of granted capabilities
    grace_period_days = Column(Integer, default=14, nullable=False)
    machine_fingerprint = Column(String(255), nullable=True)  # Hardware node-lock
    
    issued_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="license")


class LicenseHistory(Base):
    __tablename__ = "license_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    license_key_masked = Column(String(100), nullable=False)
    tier = Column(String(50), nullable=False)
    max_users = Column(Integer, nullable=False)
    storage_limit_bytes = Column(BigInteger, nullable=False)
    activated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    activated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    machine_fingerprint = Column(String(255), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="license_history")
    activated_by = relationship("User", foreign_keys=[activated_by_id])
