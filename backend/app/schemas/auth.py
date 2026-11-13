import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class DepartmentSummary(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    is_lead: bool

    model_config = ConfigDict(from_attributes=True)


class OrganizationSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    tin_number: Optional[str] = None
    logo_url: Optional[str] = None
    theme_color: str
    allowed_ip_ranges: Optional[str] = None

    # Real-time enterprise license status context
    license_tier: Optional[str] = None
    license_status: Optional[str] = None
    days_remaining: Optional[int] = None
    is_grace_period: Optional[bool] = False
    license_warning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    avatar_url: Optional[str]
    organization: OrganizationSummary
    departments: List[DepartmentSummary]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
