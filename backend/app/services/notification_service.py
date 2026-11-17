"""
EthioOffice In-App Notification Engine
Dispatches, persists, and delivers event notifications (file shares, lock changes, letter routings)
with bilingual Amharic and English localization.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationResponse, NotificationListResponse
from app.core.ethiopian_calendar import format_ethiopian_date


class NotificationService:

    @classmethod
    def create_notification(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        event_type: str,
        title: str,
        title_amharic: str,
        message: str,
        message_amharic: str,
        link: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
    ) -> Notification:
        """Dispatches and persists a new in-app notification for an employee."""
        notification = Notification(
            organization_id=org_id,
            user_id=user_id,
            actor_id=actor_id,
            event_type=event_type,
            title=title,
            title_amharic=title_amharic,
            message=message,
            message_amharic=message_amharic,
            link=link,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @classmethod
    def _to_response(cls, notif: Notification) -> NotificationResponse:
        ec_date = format_ethiopian_date(notif.created_at.date()) if notif.created_at else None
        actor_name = notif.actor.full_name if notif.actor else None
        return NotificationResponse(
            id=notif.id,
            event_type=notif.event_type,
            title=notif.title,
            title_amharic=notif.title_amharic,
            message=notif.message,
            message_amharic=notif.message_amharic,
            link=notif.link,
            is_read=notif.is_read,
            read_at=notif.read_at,
            actor_name=actor_name,
            created_at=notif.created_at,
            ec_created_at=ec_date,
        )

    @classmethod
    def list_notifications(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> NotificationListResponse:
        """Retrieves user's notifications feed with unread count."""
        base_query = db.query(Notification).filter(
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
        )

        total = base_query.count()
        unread_count = base_query.filter(Notification.is_read == False).count()

        query = base_query
        if unread_only:
            query = query.filter(Notification.is_read == False)

        items = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

        return NotificationListResponse(
            total=total,
            unread_count=unread_count,
            items=[cls._to_response(n) for n in items],
        )

    @classmethod
    def mark_as_read(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> NotificationResponse:
        """Marks a single notification as read."""
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
        ).first()

        if not notif:
            raise ValueError("ማሳወቂያው አልተገኘም (Notification not found)")

        if not notif.is_read:
            notif.is_read = True
            notif.read_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(notif)

        return cls._to_response(notif)

    @classmethod
    def mark_all_as_read(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Marks all unread notifications for the user as read."""
        now = datetime.now(timezone.utc)
        count = db.query(Notification).filter(
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).update(
            {"is_read": True, "read_at": now},
            synchronize_session=False,
        )
        db.commit()
        return count

    @classmethod
    def get_unread_count(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Returns the number of unread notifications for the user."""
        return db.query(Notification).filter(
            Notification.organization_id == org_id,
            Notification.user_id == user_id,
            Notification.is_read == False,
        ).count()
