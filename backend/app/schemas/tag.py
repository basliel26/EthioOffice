import uuid
import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field("#3b82f6", max_length=20)

    @field_validator("color")
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        clean = v.strip()
        if not re.match(r"^#(?:[0-9a-fA-F]{3}){1,2}$", clean):
            raise ValueError("ቀለሙ ትክክለኛ የሄክስ ኮድ (Hex Color Code) መሆን አለበት (e.g. #3b82f6)")
        return clean

    @field_validator("name")
    @classmethod
    def validate_tag_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("የመለያ ስም ባዶ መሆን አይችልም")
        return clean


class TagResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    color: str
    file_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileTagAssignRequest(BaseModel):
    tag_ids: List[uuid.UUID]


class FileTagResponse(BaseModel):
    file_id: uuid.UUID
    tags: List[TagResponse]
