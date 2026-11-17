"""
FastAPI Endpoints for In-App Notifications
Provides endpoints for employee event feeds, unread indicators, and read confirmations.
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List user notifications with unread counts and bilingual messaging.
    """
    return NotificationService.list_notifications(
        db=db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the badge count of unread notifications for the active user.
    """
    count = NotificationService.get_unread_count(
        db=db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
    )
    return NotificationUnreadCountResponse(unread_count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark a specific notification as read.
    """
    try:
        return NotificationService.mark_as_read(
            db=db,
            org_id=current_user.organization_id,
            user_id=current_user.id,
            notification_id=notification_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/mark-all-read")
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark all unread notifications as read.
    """
    updated_count = NotificationService.mark_all_as_read(
        db=db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
    )
    return {
        "message": "ሁሉም ማሳወቂያዎች እንደተነበቡ ተደርገዋል (All notifications marked as read)",
        "updated_count": updated_count,
    }
