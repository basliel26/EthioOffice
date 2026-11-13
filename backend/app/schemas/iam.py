import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from app.schemas.auth import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Minimum 8 characters with letters and numbers")


class SessionResponse(BaseModel):
    id: uuid.UUID
    client_ip: Optional[str]
    user_agent: Optional[str]
    last_active_at: datetime
    created_at: datetime
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters with letters and numbers")
    full_name: str = Field(..., min_length=2, max_length=150)
    role: Optional[str] = "STAFF"


class DualTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
