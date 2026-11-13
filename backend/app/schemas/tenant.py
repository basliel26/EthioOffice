import uuid
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr


class TenantBrandingPublicResponse(BaseModel):
    name: str
    slug: str
    logo_url: Optional[str]
    theme_color: str
    is_active: bool
    status: str

    model_config = ConfigDict(from_attributes=True)


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    tin_number: Optional[str] = Field(None, description="10-digit Ethiopian Tax Identification Number")
    logo_url: Optional[str] = Field(None, max_length=512)
    theme_color: Optional[str] = Field(None, description="Hex color format e.g. #059669")
    status: Optional[str] = Field(None, description="TRIAL, ACTIVE, SUSPENDED, ARCHIVED")

    @field_validator("tin_number")
    @classmethod
    def validate_tin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean_tin = v.strip()
            if not re.match(r"^\d{10}$", clean_tin):
                raise ValueError("የግብር ከፋይ መለያ ቁጥር (TIN) በትክክል 10 አሃዞች መሆን አለበት (TIN must be exactly 10 numeric digits)")
            return clean_tin
        return v

    @field_validator("theme_color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean_color = v.strip()
            if not re.match(r"^#[0-9a-fA-F]{6}$", clean_color):
                raise ValueError("የቀለም ኮድ ትክክለኛ የሄክስ (Hex) ፎርማት መሆን አለበት e.g. #059669")
            return clean_color
        return v


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    tin_number: Optional[str]
    logo_url: Optional[str]
    theme_color: str
    status: str
    max_users: int
    storage_limit_bytes: int
    used_storage_bytes: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20, description="Short uppercase code e.g. FIN, HR, LEGAL")
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = Field(None, description="Parent department ID for nested branches")
    storage_quota_gb: Optional[float] = Field(None, ge=1.0, description="Optional storage quota in GB")

    @field_validator("code")
    @classmethod
    def format_code(cls, v: str) -> str:
        return v.strip().upper()


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    storage_quota_gb: Optional[float] = None

    @field_validator("code")
    @classmethod
    def format_code(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().upper() if v else v


class DepartmentMemberResponse(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    is_lead: bool
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    description: Optional[str]
    parent_id: Optional[uuid.UUID] = None
    member_count: int = 0
    subdepartment_count: int = 0
    storage_quota_bytes: Optional[int] = None
    used_storage_bytes: int = 0
    storage_quota_gb: Optional[float] = None
    used_storage_gb: float = 0.0
    percent_used: Optional[float] = None
    leads: List[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DepartmentMemberAssignRequest(BaseModel):
    user_id: uuid.UUID
    is_lead: bool = False


class StorageQuotaResponse(BaseModel):
    used_bytes: int
    limit_bytes: int
    used_gb: float
    limit_gb: float
    percent_used: float
    is_warning: bool
    is_exceeded: bool


class TenantProvisionRequest(BaseModel):
    organization_name: str = Field(..., min_length=3, max_length=255)
    slug: str = Field(..., min_length=3, max_length=100, pattern="^[a-z0-9-]+$")
    tin_number: Optional[str] = None
    admin_email: EmailStr
    admin_full_name: str = Field(..., min_length=2)
    admin_password: str = Field(..., min_length=8)
    storage_limit_gb: float = Field(100.0, ge=1.0)
    max_users: int = Field(50, ge=1)

    @field_validator("tin_number")
    @classmethod
    def validate_tin(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean_tin = v.strip()
            if not re.match(r"^\d{10}$", clean_tin):
                raise ValueError("TIN must be exactly 10 digits")
            return clean_tin
        return v


class TenantProvisionResponse(BaseModel):
    organization_id: uuid.UUID
    name: str
    slug: str
    admin_user_id: uuid.UUID
    admin_email: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
