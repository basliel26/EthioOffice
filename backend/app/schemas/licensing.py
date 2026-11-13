"""
Pydantic schemas for Module 3: Licensing & Capability Engine
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from app.core.licensing import LicenseStatus, LicenseTier


class LicenseActivationRequest(BaseModel):
    license_key: str = Field(..., min_length=20, description="Cryptographically signed EthioOffice offline license key")


class LicenseGenerateRequest(BaseModel):
    organization_slug: str = Field(..., min_length=2, max_length=100)
    tier: LicenseTier = LicenseTier.BUSINESS
    max_users: int = Field(default=50, ge=1)
    storage_limit_gb: int = Field(default=100, ge=1)
    valid_days: int = Field(default=365, ge=1)
    grace_period_days: int = Field(default=14, ge=0)
    machine_fingerprint: Optional[str] = Field(None, description="Optional server node hardware fingerprint for node-locking")
    custom_features: Optional[List[str]] = None


class LicenseGeneratedResponse(BaseModel):
    license_key: str
    organization_slug: str
    tier: str
    max_users: int
    storage_limit_gb: int
    features: List[str]
    issued_at: datetime
    expires_at: datetime
    grace_period_days: int
    machine_fingerprint: Optional[str] = None


class CurrentLicenseResponse(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    organization_slug: str
    tier: str
    license_key_masked: str
    status: LicenseStatus
    is_usable: bool
    
    max_users: int
    active_users: int
    available_seats: int
    
    storage_limit_gb: float
    used_storage_gb: float
    storage_usage_percent: float
    
    issued_at: datetime
    expires_at: datetime
    days_remaining: int
    grace_period_days: int
    grace_days_remaining: int
    warning: Optional[str]
    machine_fingerprint: Optional[str] = None
    
    capabilities: List[str]

    model_config = ConfigDict(from_attributes=True)


class LicenseHistoryResponse(BaseModel):
    id: uuid.UUID
    license_key_masked: str
    tier: str
    max_users: int
    storage_limit_gb: float
    activated_at: datetime
    expires_at: datetime
    activated_by_email: Optional[str] = None
    machine_fingerprint: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
