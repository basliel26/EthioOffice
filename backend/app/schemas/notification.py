import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    title: str
    title_amharic: str
    message: str
    message_amharic: str
    link: Optional[str] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    actor_name: Optional[str] = None
    created_at: datetime
    ec_created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    total: int
    unread_count: int
    items: List[NotificationResponse]


class NotificationUnreadCountResponse(BaseModel):
    unread_count: int
