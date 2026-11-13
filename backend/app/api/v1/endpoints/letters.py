import uuid
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from app.core.database import get_db
from app.api.deps import get_current_user
from app.core.ethiopian_calendar import format_ethiopian_date, gregorian_to_ethiopian
from app.models.user import User
from app.models.letter import LetterRegistry, LetterDirection, LetterStatus
from app.models.audit import AuditLog, AuditAction

router = APIRouter()


class LetterCreate(BaseModel):
    reference_number: str
    direction: str  # 'INWARD' or 'OUTWARD'
    subject: str
    sender_entity: str
    recipient_entity: str
    attachment_file_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    assigned_to_id: Optional[uuid.UUID] = None


class LetterResponse(BaseModel):
    id: uuid.UUID
    reference_number: str
    direction: str
    status: str
    subject: str
    sender_entity: str
    recipient_entity: str
    date_ec: str
    date_gc: date
    attachment_file_id: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[LetterResponse])
def list_letters(
    direction: Optional[str] = Query(None, pattern="^(INWARD|OUTWARD)$"),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List and search official corporate letter registry records.
    """
    query = db.query(LetterRegistry).filter(LetterRegistry.organization_id == current_user.organization_id)

    if direction:
        query = query.filter(LetterRegistry.direction == LetterDirection(direction))
    if status:
        query = query.filter(LetterRegistry.status == LetterStatus(status))
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (LetterRegistry.reference_number.ilike(search_filter)) |
            (LetterRegistry.subject.ilike(search_filter)) |
            (LetterRegistry.sender_entity.ilike(search_filter)) |
            (LetterRegistry.recipient_entity.ilike(search_filter))
        )

    letters = query.order_by(LetterRegistry.created_at.desc()).all()
    return [
        LetterResponse(
            id=l.id,
            reference_number=l.reference_number,
            direction=l.direction.value,
            status=l.status.value,
            subject=l.subject,
            sender_entity=l.sender_entity,
            recipient_entity=l.recipient_entity,
            date_ec=l.date_ec,
            date_gc=l.date_gc,
            attachment_file_id=l.attachment_file_id,
            notes=l.notes,
            created_at=l.created_at.isoformat(),
        )
        for l in letters
    ]


@router.post("", response_model=LetterResponse)
def create_letter(
    payload: LetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register an official inward or outward company letter with automatic Ethiopian Calendar synchronization.
    """
    today = date.today()
    ec_date = format_ethiopian_date(today)

    letter = LetterRegistry(
        organization_id=current_user.organization_id,
        reference_number=payload.reference_number.strip(),
        direction=LetterDirection(payload.direction.upper()),
        status=LetterStatus.RECEIVED if payload.direction.upper() == "INWARD" else LetterStatus.DRAFT,
        subject=payload.subject.strip(),
        sender_entity=payload.sender_entity.strip(),
        recipient_entity=payload.recipient_entity.strip(),
        date_ec=ec_date,
        date_gc=today,
        attachment_file_id=payload.attachment_file_id,
        notes=payload.notes,
        created_by_id=current_user.id,
        assigned_to_id=payload.assigned_to_id or current_user.id,
    )
    db.add(letter)
    db.flush()

    audit = AuditLog(
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        action=AuditAction.LETTER_REGISTER,
        target_type="LETTER",
        target_id=letter.id,
        target_name=letter.reference_number,
        details={"subject": letter.subject, "direction": letter.direction.value}
    )
    db.add(audit)
    db.commit()
    db.refresh(letter)

    return LetterResponse(
        id=letter.id,
        reference_number=letter.reference_number,
        direction=letter.direction.value,
        status=letter.status.value,
        subject=letter.subject,
        sender_entity=letter.sender_entity,
        recipient_entity=letter.recipient_entity,
        date_ec=letter.date_ec,
        date_gc=letter.date_gc,
        attachment_file_id=letter.attachment_file_id,
        notes=letter.notes,
        created_at=letter.created_at.isoformat(),
    )
