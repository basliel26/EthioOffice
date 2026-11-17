import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class LetterAttachmentCreate(BaseModel):
    file_id: uuid.UUID
    attachment_type: str = Field("SUPPORTING_DOCUMENT", pattern="^(PRIMARY_SIGNED_PDF|SUPPORTING_DOCUMENT|ANNEX)$")
    notes: Optional[str] = None


class LetterAttachmentResponse(BaseModel):
    id: uuid.UUID
    letter_id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    mime_type: Optional[str] = None
    size_bytes: int = 0
    attachment_type: str
    notes: Optional[str] = None
    attached_by_name: Optional[str] = None
    created_at: datetime
    ec_created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
