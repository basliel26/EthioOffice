"""
EthioOffice Sharing & Access Control Pydantic Schemas (Module 6)
Defines request and response models for internal user/department sharing
and external tokenized public link sharing.
"""

import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from app.models.share import SharePermission
from app.models.share_link import LinkAccessType


# =====================================================================
# Internal User & Department Sharing Schemas
# =====================================================================

class ShareCreateRequest(BaseModel):
    target_user_id: Optional[uuid.UUID] = None
    target_department_id: Optional[uuid.UUID] = None
    permission: str = Field(default="VIEWER", pattern="^(VIEWER|EDITOR)$")
    expires_at: Optional[datetime] = None


class ShareResponse(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    is_folder: bool
    shared_by_id: uuid.UUID
    shared_by_name: str
    target_user_id: Optional[uuid.UUID] = None
    target_user_name: Optional[str] = None
    target_department_id: Optional[uuid.UUID] = None
    target_department_name: Optional[str] = None
    permission: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    ec_created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =====================================================================
# External Public Link Sharing Schemas
# =====================================================================

class ShareLinkCreateRequest(BaseModel):
    access_type: str = Field(default="ALLOW_DOWNLOAD", pattern="^(VIEW_ONLY|ALLOW_DOWNLOAD|UPLOAD_DROPBOX)$")
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = Field(default=None, ge=1)


class ShareLinkResponse(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    is_folder: bool
    token: str
    access_type: str
    is_password_protected: bool
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None
    download_count: int
    is_active: bool
    created_at: datetime
    ec_created_at: Optional[str] = None
    public_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PublicLinkMetadataResponse(BaseModel):
    token: str
    file_name: str
    is_folder: bool
    size_bytes: int
    mime_type: Optional[str] = None
    access_type: str
    is_password_protected: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    ec_created_at: Optional[str] = None


class PublicLinkVerifyRequest(BaseModel):
    password: str = Field(..., min_length=1)


class PublicLinkAccessSession(BaseModel):
    token: str
    access_granted: bool
    message: str
