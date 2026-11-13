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
    tin_number: Optional[str]
    logo_url: Optional[str]
    theme_color: str

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
