import uuid
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.letter import (
    LetterDirection,
    LetterStatus,
    LetterConfidentiality,
    LetterUrgency,
    DeliveryMethod,
    RoutingAction,
    RoutingStatus,
)
from app.schemas.letter_attachment import LetterAttachmentResponse


class LetterRoutingCreate(BaseModel):
    to_department_id: uuid.UUID
    to_user_id: Optional[uuid.UUID] = None
    action_required: RoutingAction = RoutingAction.FOR_ACTION
    priority: Optional[LetterUrgency] = LetterUrgency.NORMAL
    instructions: Optional[str] = None


class LetterRoutingComplete(BaseModel):
    response_notes: str = Field(..., min_length=1)


class LetterRoutingResponse(BaseModel):
    id: uuid.UUID
    letter_id: uuid.UUID
    from_user_id: uuid.UUID
    from_user_name: Optional[str] = None
    from_department_id: Optional[uuid.UUID] = None
    from_department_name: Optional[str] = None
    to_user_id: Optional[uuid.UUID] = None
    to_user_name: Optional[str] = None
    to_department_id: uuid.UUID
    to_department_name: Optional[str] = None
    transferred_at: datetime
    action_required: RoutingAction
    priority: LetterUrgency
    instructions: Optional[str] = None
    status: RoutingStatus
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    response_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class LetterCreate(BaseModel):
    direction: LetterDirection = LetterDirection.INWARD
    department_id: Optional[uuid.UUID] = None
    subject: str = Field(..., min_length=2, max_length=500)
    sender_entity: str = Field(..., min_length=2, max_length=255)
    sender_contact: Optional[str] = None
    recipient_entity: str = Field(..., min_length=2, max_length=255)
    recipient_contact: Optional[str] = None
    cc_entities: Optional[List[str]] = None
    confidentiality: LetterConfidentiality = LetterConfidentiality.NORMAL
    urgency: LetterUrgency = LetterUrgency.NORMAL
    delivery_method: Optional[DeliveryMethod] = None
    reference_number: Optional[str] = None  # If omitted, auto-generated
    external_reference_number: Optional[str] = None
    date_gc: Optional[date] = None
    attachment_file_id: Optional[uuid.UUID] = None
    reply_to_letter_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    assigned_to_id: Optional[uuid.UUID] = None


class LetterUpdate(BaseModel):
    subject: Optional[str] = Field(None, min_length=2, max_length=500)
    sender_entity: Optional[str] = Field(None, min_length=2, max_length=255)
    sender_contact: Optional[str] = None
    recipient_entity: Optional[str] = Field(None, min_length=2, max_length=255)
    recipient_contact: Optional[str] = None
    cc_entities: Optional[List[str]] = None
    confidentiality: Optional[LetterConfidentiality] = None
    urgency: Optional[LetterUrgency] = None
    delivery_method: Optional[DeliveryMethod] = None
    attachment_file_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    assigned_to_id: Optional[uuid.UUID] = None


class LetterApprovalRequest(BaseModel):
    action: str = Field(..., pattern="^(APPROVE|REJECT)$")
    rejection_reason: Optional[str] = None


class LetterDispatchRequest(BaseModel):
    delivery_method: Optional[DeliveryMethod] = DeliveryMethod.HAND_DELIVERY
    dispatched_date_gc: Optional[date] = None


class LetterResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    reference_number: str
    external_reference_number: Optional[str] = None
    direction: LetterDirection
    status: LetterStatus
    confidentiality: LetterConfidentiality
    urgency: LetterUrgency
    delivery_method: Optional[DeliveryMethod] = None
    subject: str
    sender_entity: str
    sender_contact: Optional[str] = None
    recipient_entity: str
    recipient_contact: Optional[str] = None
    cc_entities: Optional[List[str]] = None
    date_ec: str
    date_gc: date
    ethiopian_year: Optional[int] = None
    due_date_gc: Optional[date] = None
    due_date_ec: Optional[str] = None
    is_overdue: bool = False
    days_remaining: Optional[int] = None
    approved_at_gc: Optional[datetime] = None
    approved_by_id: Optional[uuid.UUID] = None
    rejected_at_gc: Optional[datetime] = None
    rejected_by_id: Optional[uuid.UUID] = None
    rejection_reason: Optional[str] = None
    dispatched_at_gc: Optional[datetime] = None
    dispatched_at_ec: Optional[str] = None
    dispatched_by_id: Optional[uuid.UUID] = None
    attachment_file_id: Optional[uuid.UUID] = None
    attachment_filename: Optional[str] = None
    reply_to_letter_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_by_id: Optional[uuid.UUID] = None
    assigned_to_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LetterDetailResponse(LetterResponse):
    routings: List[LetterRoutingResponse] = []
    attachments: List[LetterAttachmentResponse] = []
    reply_count: int = 0


class LetterAnalyticsSummary(BaseModel):
    total_letters: int
    inward_count: int
    outward_count: int
    memo_count: int
    pending_approval_count: int
    dispatched_count: int
    received_count: int
    archived_count: int
    urgent_open_count: int
    overdue_sla_count: int
    confidential_count: int
    by_department: Dict[str, int]
    by_urgency: Dict[str, int]
