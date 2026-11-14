import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.letter import (
    LetterDirection,
    LetterStatus,
    LetterConfidentiality,
    LetterUrgency,
)
from app.schemas.letter import (
    LetterCreate,
    LetterUpdate,
    LetterResponse,
    LetterDetailResponse,
    LetterRoutingCreate,
    LetterRoutingComplete,
    LetterRoutingResponse,
    LetterApprovalRequest,
    LetterDispatchRequest,
    LetterAnalyticsSummary,
)
from app.services.letter_service import LetterService
from app.services.capability_service import require_capability, Capability

router = APIRouter(dependencies=[Depends(require_capability(Capability.LETTER_REGISTRY))])


@router.get("/analytics/summary", response_model=LetterAnalyticsSummary)
def get_letter_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get executive-level metrics and SLA status for the organization's official letter registry.
    """
    return LetterService.get_analytics_summary(db=db, user=current_user)


@router.get("", response_model=List[LetterResponse])
def list_letters(
    direction: Optional[LetterDirection] = Query(None, description="Filter by direction: INWARD, OUTWARD, INTERNAL_MEMO"),
    status: Optional[LetterStatus] = Query(None, description="Filter by status"),
    confidentiality: Optional[LetterConfidentiality] = Query(None, description="Filter by security classification"),
    urgency: Optional[LetterUrgency] = Query(None, description="Filter by urgency level"),
    department_id: Optional[uuid.UUID] = Query(None, description="Filter by issuing/owning department"),
    ethiopian_year: Optional[int] = Query(None, description="Filter by Ethiopian fiscal year (e.g. 2018)"),
    search: Optional[str] = Query(None, description="Search by ref number, subject, sender, or recipient (Amharic normalized)"),
    is_overdue: Optional[bool] = Query(None, description="Filter letters breaching Ethiopian working day SLA"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List and search official corporate letter registry records with RBAC security clearance.
    """
    return LetterService.list_letters(
        db=db,
        user=current_user,
        direction=direction,
        status_filter=status,
        confidentiality=confidentiality,
        urgency=urgency,
        department_id=department_id,
        ethiopian_year=ethiopian_year,
        search=search,
        is_overdue=is_overdue,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=LetterResponse)
def create_letter(
    payload: LetterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register an official inward, outward, or internal letter with atomic sequence numbering and Ethiopian Calendar SLA.
    """
    letter = LetterService.register_letter(db=db, user=current_user, payload=payload)
    detail = LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)
    return detail


@router.get("/{id}", response_model=LetterDetailResponse)
def get_letter_detail(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve full letter details, including departmental routing history and attachment metadata.
    """
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=id)


@router.patch("/{id}", response_model=LetterResponse)
def update_letter(
    id: uuid.UUID,
    payload: LetterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update editable fields of an open or draft letter.
    """
    letter = LetterService.update_letter(db=db, user=current_user, letter_id=id, payload=payload)
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)


@router.post("/{id}/submit", response_model=LetterResponse)
def submit_letter_for_approval(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an outward draft letter for manager/administrator approval.
    """
    letter = LetterService.submit_for_approval(db=db, user=current_user, letter_id=id)
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)


@router.post("/{id}/approve", response_model=LetterResponse)
def approve_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve an outward letter draft. Requires Organization Admin or Department Lead privilege.
    """
    letter = LetterService.approve_letter(db=db, user=current_user, letter_id=id)
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)


@router.post("/{id}/reject", response_model=LetterResponse)
def reject_letter(
    id: uuid.UUID,
    payload: LetterApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reject an outward letter draft with reviewer feedback.
    """
    letter = LetterService.reject_letter(
        db=db,
        user=current_user,
        letter_id=id,
        reason=payload.rejection_reason or "Changes requested",
    )
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)


@router.post("/{id}/dispatch", response_model=LetterResponse)
def dispatch_letter(
    id: uuid.UUID,
    payload: LetterDispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark an approved outward letter as dispatched, recording dispatch date and delivery method.
    """
    letter = LetterService.dispatch_letter(
        db=db,
        user=current_user,
        letter_id=id,
        delivery_method=payload.delivery_method or LetterUrgency.NORMAL,
        dispatched_date_gc=payload.dispatched_date_gc,
    )
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)


@router.post("/{id}/route", response_model=LetterRoutingResponse)
def route_letter(
    id: uuid.UUID,
    payload: LetterRoutingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transfer/forward a letter to another department with chain-of-custody instructions.
    """
    routing = LetterService.route_letter(db=db, user=current_user, letter_id=id, payload=payload)
    detail = LetterService.get_letter_detail(db=db, user=current_user, letter_id=id)
    # Find the created routing in detail.routings
    created = next((r for r in detail.routings if r.id == routing.id), None)
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created routing")
    return created


@router.patch("/routings/{routing_id}/acknowledge", response_model=LetterRoutingResponse)
def acknowledge_letter_routing(
    routing_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Acknowledge receipt of a routed letter by the destination department officer.
    """
    routing = LetterService.acknowledge_routing(db=db, user=current_user, routing_id=routing_id)
    detail = LetterService.get_letter_detail(db=db, user=current_user, letter_id=routing.letter_id)
    updated = next((r for r in detail.routings if r.id == routing.id), None)
    return updated


@router.patch("/routings/{routing_id}/complete", response_model=LetterRoutingResponse)
def complete_letter_routing(
    routing_id: uuid.UUID,
    payload: LetterRoutingComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a letter routing task as completed with resolution notes.
    """
    routing = LetterService.complete_routing(
        db=db,
        user=current_user,
        routing_id=routing_id,
        response_notes=payload.response_notes,
    )
    detail = LetterService.get_letter_detail(db=db, user=current_user, letter_id=routing.letter_id)
    updated = next((r for r in detail.routings if r.id == routing.id), None)
    return updated


@router.post("/{id}/archive", response_model=LetterResponse)
def archive_letter(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Archive a letter in the registry.
    """
    letter = LetterService.archive_letter(db=db, user=current_user, letter_id=id)
    return LetterService.get_letter_detail(db=db, user=current_user, letter_id=letter.id)
