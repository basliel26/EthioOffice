import uuid
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    tin_number: Optional[str] = Field(None, description="10-digit Ethiopian Tax Identification Number")
    logo_url: Optional[str] = Field(None, max_length=512)
    theme_color: Optional[str] = Field(None, description="Hex color format e.g. #059669")

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

    @field_validator("code")
    @classmethod
    def format_code(cls, v: str) -> str:
        return v.strip().upper()


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = None

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
    member_count: int = 0
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
