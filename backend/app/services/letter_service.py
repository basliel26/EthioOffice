import uuid
from datetime import date, datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from fastapi import HTTPException, status

from app.models.letter import (
    LetterRegistry,
    LetterSequence,
    LetterRouting,
    LetterDirection,
    LetterStatus,
    LetterConfidentiality,
    LetterUrgency,
    DeliveryMethod,
    RoutingAction,
    RoutingStatus,
)
from app.models.user import User, UserRole
from app.models.department import Department, UserDepartment
from app.models.organization import Organization
from app.models.file import FileItem
from app.models.audit import AuditLog, AuditAction
from app.models.letter_attachment import LetterAttachment
from app.services.localization_service import LocalizationService
from app.services.capability_service import CapabilityService
from app.core.ethiopian_calendar import format_ethiopian_date
from app.schemas.letter_attachment import LetterAttachmentResponse
from app.schemas.letter import (
    LetterCreate,
    LetterUpdate,
    LetterRoutingCreate,
    LetterResponse,
    LetterDetailResponse,
    LetterRoutingResponse,
    LetterAnalyticsSummary,
)


class LetterService:

    @staticmethod
    def _is_admin(user: User) -> bool:
        return user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    @staticmethod
    def _is_department_lead(db: Session, user: User, department_id: Optional[uuid.UUID]) -> bool:
        if not department_id:
            return False
        if user.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN):
            return True
        membership = db.query(UserDepartment).filter(
            UserDepartment.user_id == user.id,
            UserDepartment.department_id == department_id,
            UserDepartment.is_department_lead == True,
        ).first()
        return membership is not None

    @classmethod
    def check_letter_access(cls, letter: LetterRegistry, user: User, db: Session) -> bool:
        """
        Evaluate RBAC access to a letter according to its confidentiality clearance level.
        """
        # Super Admins and Org Admins have full access
        if cls._is_admin(user):
            return True

        # NORMAL confidentiality: accessible to all members of the organization
        if letter.confidentiality == LetterConfidentiality.NORMAL:
            return letter.organization_id == user.organization_id

        # STRICTLY_CONFIDENTIAL: strictly author, assignee, or admin
        if letter.confidentiality == LetterConfidentiality.STRICTLY_CONFIDENTIAL:
            return (
                letter.created_by_id == user.id or
                letter.assigned_to_id == user.id
            )

        # CONFIDENTIAL: author, assignee, department leads, or routing chain participants
        if letter.confidentiality == LetterConfidentiality.CONFIDENTIAL:
            if letter.created_by_id == user.id or letter.assigned_to_id == user.id:
                return True

            # Check if user is lead of the letter's department
            if letter.department_id and cls._is_department_lead(db, user, letter.department_id):
                return True

            # Check if user is sender, recipient, or lead of destination department in any routing record
            routings = db.query(LetterRouting).filter(LetterRouting.letter_id == letter.id).all()
            for r in routings:
                if r.from_user_id == user.id or r.to_user_id == user.id:
                    return True
                if cls._is_department_lead(db, user, r.to_department_id):
                    return True

            return False

        return False

    @classmethod
    def generate_reference_number(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        department_id: Optional[uuid.UUID],
        direction: LetterDirection,
        fiscal_year: int,
    ) -> str:
        """
        Atomically generate a tamper-proof sequential reference number using PostgreSQL native atomic upsert.
        """
        from sqlalchemy import text
        org = db.query(Organization).filter(Organization.id == organization_id).first()
        org_prefix = org.slug.upper().replace("-", "")[:4] if org else "EO"

        dept_code = "GEN"
        if department_id:
            dept = db.query(Department).filter(Department.id == department_id).first()
            if dept and dept.code:
                dept_code = dept.code.upper()

        upsert_sql = text("""
        INSERT INTO letter_sequences (
            id, organization_id, department_id, fiscal_year, counter_type,
            current_number, prefix, format_pattern, created_at, updated_at
        ) VALUES (
            :id, :org_id, :dept_id, :fiscal_year, :counter_type,
            1, :prefix, :format_pattern, NOW(), NOW()
        )
        ON CONFLICT (organization_id, COALESCE(department_id, '00000000-0000-0000-0000-000000000000'::uuid), fiscal_year, counter_type)
        DO UPDATE SET 
            current_number = letter_sequences.current_number + 1,
            updated_at = NOW()
        RETURNING current_number, prefix, format_pattern;
        """)

        res = db.execute(upsert_sql, {
            "id": uuid.uuid4(),
            "org_id": organization_id,
            "dept_id": department_id,
            "fiscal_year": fiscal_year,
            "counter_type": direction.value,
            "prefix": org_prefix,
            "format_pattern": "{ORG}/{DEPT}/{YEAR}/{SEQ:04d}",
        }).first()

        current_num = res[0]
        fmt_pattern = res[2] or "{ORG}/{DEPT}/{YEAR}/{SEQ:04d}"

        geez_year = LocalizationService.arabic_to_geez(fiscal_year)
        geez_seq = LocalizationService.arabic_to_geez(current_num)

        formatted = fmt_pattern.format(
            ORG=org_prefix,
            DEPT=dept_code,
            YEAR=fiscal_year,
            SEQ=current_num,
            GEEZ_YEAR=geez_year,
            GEEZ_SEQ=geez_seq,
        )
        return formatted

    @classmethod
    def compute_sla(
        cls,
        start_date: date,
        urgency: LetterUrgency,
    ) -> Tuple[date, str]:
        """
        Compute due date GC and due date EC based on urgency level and Ethiopian working days.
        """
        if urgency == LetterUrgency.VERY_URGENT:
            working_days = 1
        elif urgency == LetterUrgency.URGENT:
            working_days = 3
        else:
            working_days = 5

        sla_resp = LocalizationService.add_working_days(
            start_date=start_date,
            days_to_add=working_days,
        )
        return sla_resp.target_date, sla_resp.target_date_ethiopian

    @classmethod
    def register_letter(
        cls,
        db: Session,
        user: User,
        payload: LetterCreate,
    ) -> LetterRegistry:
        """
        Register a new inward, outward, or internal corporate letter.
        """
        letter_date_gc = payload.date_gc or date.today()
        date_conv = LocalizationService.format_date_conversion(letter_date_gc)
        date_ec = date_conv.formatted_amharic
        ec_year = date_conv.ethiopian_year

        # Department validation
        if payload.department_id:
            dept = db.query(Department).filter(
                Department.id == payload.department_id,
                Department.organization_id == user.organization_id,
            ).first()
            if not dept:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Specified department not found")

        # Attachment validation
        if payload.attachment_file_id:
            file_item = db.query(FileItem).filter(
                FileItem.id == payload.attachment_file_id,
                FileItem.organization_id == user.organization_id,
                FileItem.is_deleted == False,
            ).first()
            if not file_item:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found")

        # Reference Number Generation
        if payload.reference_number and payload.reference_number.strip():
            ref_number = payload.reference_number.strip()
        else:
            ref_number = cls.generate_reference_number(
                db=db,
                organization_id=user.organization_id,
                department_id=payload.department_id,
                direction=payload.direction,
                fiscal_year=ec_year,
            )

        # Calculate SLA
        due_date_gc, due_date_ec = cls.compute_sla(letter_date_gc, payload.urgency)

        # Determine initial status
        if payload.direction == LetterDirection.OUTWARD:
            initial_status = LetterStatus.DRAFT
        else:
            initial_status = LetterStatus.RECEIVED

        letter = LetterRegistry(
            organization_id=user.organization_id,
            department_id=payload.department_id,
            reference_number=ref_number,
            external_reference_number=payload.external_reference_number.strip() if payload.external_reference_number else None,
            direction=payload.direction,
            status=initial_status,
            confidentiality=payload.confidentiality,
            urgency=payload.urgency,
            delivery_method=payload.delivery_method,
            subject=payload.subject.strip(),
            sender_entity=payload.sender_entity.strip(),
            sender_contact=payload.sender_contact.strip() if payload.sender_contact else None,
            recipient_entity=payload.recipient_entity.strip(),
            recipient_contact=payload.recipient_contact.strip() if payload.recipient_contact else None,
            cc_entities=payload.cc_entities,
            date_ec=date_ec,
            date_gc=letter_date_gc,
            ethiopian_year=ec_year,
            due_date_gc=due_date_gc,
            due_date_ec=due_date_ec,
            attachment_file_id=payload.attachment_file_id,
            reply_to_letter_id=payload.reply_to_letter_id,
            notes=payload.notes,
            created_by_id=user.id,
            assigned_to_id=payload.assigned_to_id or user.id,
        )
        db.add(letter)
        db.flush()

        # Audit log
        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_REGISTER,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={
                "subject": letter.subject,
                "direction": letter.direction.value,
                "confidentiality": letter.confidentiality.value,
                "urgency": letter.urgency.value,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(letter)
        return letter

    @classmethod
    def update_letter(
        cls,
        db: Session,
        user: User,
        letter_id: uuid.UUID,
        payload: LetterUpdate,
    ) -> LetterRegistry:
        """
        Update draft or open letter metadata.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: security clearance required")

        if letter.status in (LetterStatus.DISPATCHED, LetterStatus.ARCHIVED) and not cls._is_admin(user):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit dispatched or archived letters")

        if payload.subject is not None:
            letter.subject = payload.subject.strip()
        if payload.sender_entity is not None:
            letter.sender_entity = payload.sender_entity.strip()
        if payload.sender_contact is not None:
            letter.sender_contact = payload.sender_contact.strip()
        if payload.recipient_entity is not None:
            letter.recipient_entity = payload.recipient_entity.strip()
        if payload.recipient_contact is not None:
            letter.recipient_contact = payload.recipient_contact.strip()
        if payload.cc_entities is not None:
            letter.cc_entities = payload.cc_entities
        if payload.confidentiality is not None:
            letter.confidentiality = payload.confidentiality
        if payload.urgency is not None:
            letter.urgency = payload.urgency
            due_gc, due_ec = cls.compute_sla(letter.date_gc, letter.urgency)
            letter.due_date_gc = due_gc
            letter.due_date_ec = due_ec
        if payload.delivery_method is not None:
            letter.delivery_method = payload.delivery_method
        if payload.attachment_file_id is not None:
            letter.attachment_file_id = payload.attachment_file_id
        if payload.notes is not None:
            letter.notes = payload.notes
        if payload.assigned_to_id is not None:
            letter.assigned_to_id = payload.assigned_to_id

        letter.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(letter)
        return letter

    @classmethod
    def submit_for_approval(cls, db: Session, user: User, letter_id: uuid.UUID) -> LetterRegistry:
        """
        Submit outward letter draft for managerial approval.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if letter.direction != LetterDirection.OUTWARD:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only outward letters require approval")

        if letter.status not in (LetterStatus.DRAFT, LetterStatus.REJECTED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Letter in status '{letter.status.value}' cannot be submitted for approval",
            )

        letter.status = LetterStatus.PENDING_APPROVAL
        letter.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(letter)
        return letter

    @classmethod
    def approve_letter(cls, db: Session, user: User, letter_id: uuid.UUID) -> LetterRegistry:
        """
        Approve an outward letter draft. Requires Org Admin or Department Lead.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        # Authorization: Must be Admin or Lead of the letter's department
        is_authorized = cls._is_admin(user) or cls._is_department_lead(db, user, letter.department_id)
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approval requires Organization Administrator or Department Lead privileges",
            )

        if letter.status != LetterStatus.PENDING_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve letter with status '{letter.status.value}'. Must be PENDING_APPROVAL",
            )

        letter.status = LetterStatus.APPROVED
        letter.approved_at_gc = datetime.now(timezone.utc)
        letter.approved_by_id = user.id
        letter.rejection_reason = None
        letter.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_APPROVE,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={"approved_by": user.full_name},
        )
        db.add(audit)
        db.commit()
        db.refresh(letter)

        # Notify letter author of approval
        try:
            from app.services.notification_service import NotificationService
            if letter.created_by_id and letter.created_by_id != user.id:
                NotificationService.create_notification(
                    db=db,
                    org_id=user.organization_id,
                    user_id=letter.created_by_id,
                    actor_id=user.id,
                    event_type="LETTER_APPROVED",
                    title=f"Letter Approved: {letter.reference_number}",
                    title_amharic=f"ደብዳቤ ጸድቋል፦ {letter.reference_number}",
                    message=f"Your outward letter '{letter.subject}' was approved by {user.full_name}.",
                    message_amharic=f"የደብዳቤ ረቂቅዎ '{letter.subject}' በ{user.full_name} ጸድቋል::",
                    link=f"/letters/{letter.id}",
                )
        except Exception:
            pass

        return letter

    @classmethod
    def reject_letter(cls, db: Session, user: User, letter_id: uuid.UUID, reason: str) -> LetterRegistry:
        """
        Reject an outward letter draft with feedback notes.
        """
        if not reason or not reason.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection reason is required")

        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        is_authorized = cls._is_admin(user) or cls._is_department_lead(db, user, letter.department_id)
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rejection requires Organization Administrator or Department Lead privileges",
            )

        if letter.status != LetterStatus.PENDING_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject letter in status '{letter.status.value}'",
            )

        letter.status = LetterStatus.REJECTED
        letter.rejected_at_gc = datetime.now(timezone.utc)
        letter.rejected_by_id = user.id
        letter.rejection_reason = reason.strip()
        letter.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_REJECT,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={"rejected_by": user.full_name, "reason": reason.strip()},
        )
        db.add(audit)
        db.commit()
        db.refresh(letter)

        # Notify letter author of rejection
        try:
            from app.services.notification_service import NotificationService
            if letter.created_by_id and letter.created_by_id != user.id:
                NotificationService.create_notification(
                    db=db,
                    org_id=user.organization_id,
                    user_id=letter.created_by_id,
                    actor_id=user.id,
                    event_type="LETTER_REJECTED",
                    title=f"Letter Returned/Rejected: {letter.reference_number}",
                    title_amharic=f"ደብዳቤ አልተፈቀደም / ተመልሷል፦ {letter.reference_number}",
                    message=f"Your outward letter '{letter.subject}' was rejected by {user.full_name}. Reason: {reason.strip()}",
                    message_amharic=f"የደብዳቤ ረቂቅዎ '{letter.subject}' በ{user.full_name} አልጸደቀም:: ምክንያት፦ {reason.strip()}",
                    link=f"/letters/{letter.id}",
                )
        except Exception:
            pass

        return letter

    @classmethod
    def dispatch_letter(
        cls,
        db: Session,
        user: User,
        letter_id: uuid.UUID,
        delivery_method: DeliveryMethod = DeliveryMethod.HAND_DELIVERY,
        dispatched_date_gc: Optional[date] = None,
    ) -> LetterRegistry:
        """
        Dispatch an approved outward letter. Stamps dispatch metadata and Ethiopian timestamp.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        if letter.direction == LetterDirection.OUTWARD and letter.status != LetterStatus.APPROVED and not cls._is_admin(user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Outward letters must be APPROVED before dispatch",
            )

        now = datetime.now(timezone.utc)
        disp_date = dispatched_date_gc or now.date()
        disp_conv = LocalizationService.format_date_conversion(disp_date)
        dispatched_at_ec = disp_conv.formatted_amharic

        letter.status = LetterStatus.DISPATCHED
        letter.delivery_method = delivery_method
        letter.dispatched_at_gc = now
        letter.dispatched_at_ec = dispatched_at_ec
        letter.dispatched_by_id = user.id
        letter.updated_at = now

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_DISPATCH,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={
                "delivery_method": delivery_method.value,
                "dispatched_at_ec": dispatched_at_ec,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(letter)
        return letter

    @classmethod
    def route_letter(
        cls,
        db: Session,
        user: User,
        letter_id: uuid.UUID,
        payload: LetterRoutingCreate,
    ) -> LetterRouting:
        """
        Transfer/Forward letter to another department (Chain of Custody).
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        # Destination department verification
        dest_dept = db.query(Department).filter(
            Department.id == payload.to_department_id,
            Department.organization_id == user.organization_id,
        ).first()
        if not dest_dept:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination department not found")

        # Destination user verification
        if payload.to_user_id:
            dest_user = db.query(User).filter(
                User.id == payload.to_user_id,
                User.organization_id == user.organization_id,
            ).first()
            if not dest_user:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Destination user not found")

        # Get sender's primary department
        sender_dept = db.query(UserDepartment).filter(
            UserDepartment.user_id == user.id,
        ).first()
        from_dept_id = sender_dept.department_id if sender_dept else letter.department_id

        routing = LetterRouting(
            letter_id=letter.id,
            organization_id=user.organization_id,
            from_user_id=user.id,
            from_department_id=from_dept_id,
            to_user_id=payload.to_user_id,
            to_department_id=payload.to_department_id,
            action_required=payload.action_required,
            priority=payload.priority or letter.urgency,
            instructions=payload.instructions.strip() if payload.instructions else None,
            status=RoutingStatus.PENDING,
        )
        db.add(routing)

        # Update assigned staff on the letter if specified
        if payload.to_user_id:
            letter.assigned_to_id = payload.to_user_id
        letter.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_ROUTE,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={
                "to_department": dest_dept.name,
                "action_required": routing.action_required.value,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(routing)

        # Notify recipient if assigned to a specific user
        try:
            from app.services.notification_service import NotificationService
            if payload.to_user_id and payload.to_user_id != user.id:
                NotificationService.create_notification(
                    db=db,
                    org_id=user.organization_id,
                    user_id=payload.to_user_id,
                    actor_id=user.id,
                    event_type="LETTER_ROUTED",
                    title=f"Letter Forwarded: {letter.reference_number}",
                    title_amharic=f"ደብዳቤ ተመርቶልዎታል፦ {letter.reference_number}",
                    message=f"Letter '{letter.subject}' was transferred to you by {user.full_name} for action: {routing.action_required.value}.",
                    message_amharic=f"ደብዳቤ '{letter.subject}' በ{user.full_name} ለ{routing.action_required.value} እርምጃ ተመርቶልዎታል::",
                    link=f"/letters/{letter.id}",
                )
        except Exception:
            pass

        return routing

    @classmethod
    def acknowledge_routing(cls, db: Session, user: User, routing_id: uuid.UUID) -> LetterRouting:
        """
        Acknowledge receipt of a routed letter.
        """
        routing = db.query(LetterRouting).filter(
            LetterRouting.id == routing_id,
            LetterRouting.organization_id == user.organization_id,
        ).first()
        if not routing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing record not found")

        # Verify recipient or department lead
        is_recipient = routing.to_user_id == user.id
        is_dept_lead = cls._is_department_lead(db, user, routing.to_department_id)
        if not (is_recipient or is_dept_lead or cls._is_admin(user)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the designated recipient, department lead, or admin can acknowledge this transfer",
            )

        routing.status = RoutingStatus.ACKNOWLEDGED
        routing.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(routing)
        return routing

    @classmethod
    def complete_routing(cls, db: Session, user: User, routing_id: uuid.UUID, response_notes: str) -> LetterRouting:
        """
        Mark a routing action as completed with resolution notes.
        """
        routing = db.query(LetterRouting).filter(
            LetterRouting.id == routing_id,
            LetterRouting.organization_id == user.organization_id,
        ).first()
        if not routing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Routing record not found")

        is_recipient = routing.to_user_id == user.id
        is_dept_lead = cls._is_department_lead(db, user, routing.to_department_id)
        if not (is_recipient or is_dept_lead or cls._is_admin(user)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the designated recipient, department lead, or admin can complete this transfer",
            )

        routing.status = RoutingStatus.COMPLETED
        routing.completed_at = datetime.now(timezone.utc)
        routing.response_notes = response_notes.strip()
        db.commit()
        db.refresh(routing)
        return routing

    @classmethod
    def archive_letter(cls, db: Session, user: User, letter_id: uuid.UUID) -> LetterRegistry:
        """
        Archive a letter in the registry.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        letter.status = LetterStatus.ARCHIVED
        letter.updated_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LETTER_ARCHIVE,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={"archived_by": user.full_name},
        )
        db.add(audit)
        db.commit()
        db.refresh(letter)
        return letter

    @classmethod
    def get_letter_detail(cls, db: Session, user: User, letter_id: uuid.UUID) -> LetterDetailResponse:
        """
        Retrieve complete letter details with routing history and replies count.
        """
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == user.organization_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Letter not found")

        if not cls.check_letter_access(letter, user, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: security clearance required")

        # Calculate SLA details
        today = date.today()
        is_overdue = False
        days_remaining = None
        if letter.due_date_gc and letter.status not in (LetterStatus.ARCHIVED, LetterStatus.DISPATCHED):
            days_remaining = (letter.due_date_gc - today).days
            is_overdue = days_remaining < 0

        # Routing trail
        routings = db.query(LetterRouting).filter(
            LetterRouting.letter_id == letter.id,
        ).order_by(LetterRouting.transferred_at.desc()).all()

        routing_responses = []
        for r in routings:
            from_u = db.query(User).filter(User.id == r.from_user_id).first()
            from_d = db.query(Department).filter(Department.id == r.from_department_id).first() if r.from_department_id else None
            to_u = db.query(User).filter(User.id == r.to_user_id).first() if r.to_user_id else None
            to_d = db.query(Department).filter(Department.id == r.to_department_id).first()

            routing_responses.append(
                LetterRoutingResponse(
                    id=r.id,
                    letter_id=r.letter_id,
                    from_user_id=r.from_user_id,
                    from_user_name=from_u.full_name if from_u else None,
                    from_department_id=r.from_department_id,
                    from_department_name=from_d.name if from_d else None,
                    to_user_id=r.to_user_id,
                    to_user_name=to_u.full_name if to_u else None,
                    to_department_id=r.to_department_id,
                    to_department_name=to_d.name if to_d else None,
                    transferred_at=r.transferred_at,
                    action_required=r.action_required,
                    priority=r.priority,
                    instructions=r.instructions,
                    status=r.status,
                    acknowledged_at=r.acknowledged_at,
                    completed_at=r.completed_at,
                    response_notes=r.response_notes,
                )
            )

        # Department name
        dept = db.query(Department).filter(Department.id == letter.department_id).first() if letter.department_id else None
        # Attachment filename
        attach = db.query(FileItem).filter(FileItem.id == letter.attachment_file_id).first() if letter.attachment_file_id else None

        # Reply count
        reply_count = db.query(func.count(LetterRegistry.id)).filter(
            LetterRegistry.reply_to_letter_id == letter.id,
        ).scalar() or 0

        return LetterDetailResponse(
            id=letter.id,
            organization_id=letter.organization_id,
            department_id=letter.department_id,
            department_name=dept.name if dept else None,
            reference_number=letter.reference_number,
            external_reference_number=letter.external_reference_number,
            direction=letter.direction,
            status=letter.status,
            confidentiality=letter.confidentiality,
            urgency=letter.urgency,
            delivery_method=letter.delivery_method,
            subject=letter.subject,
            sender_entity=letter.sender_entity,
            sender_contact=letter.sender_contact,
            recipient_entity=letter.recipient_entity,
            recipient_contact=letter.recipient_contact,
            cc_entities=letter.cc_entities,
            date_ec=letter.date_ec,
            date_gc=letter.date_gc,
            ethiopian_year=letter.ethiopian_year,
            due_date_gc=letter.due_date_gc,
            due_date_ec=letter.due_date_ec,
            is_overdue=is_overdue,
            days_remaining=days_remaining,
            approved_at_gc=letter.approved_at_gc,
            approved_by_id=letter.approved_by_id,
            rejected_at_gc=letter.rejected_at_gc,
            rejected_by_id=letter.rejected_by_id,
            rejection_reason=letter.rejection_reason,
            dispatched_at_gc=letter.dispatched_at_gc,
            dispatched_at_ec=letter.dispatched_at_ec,
            dispatched_by_id=letter.dispatched_by_id,
            attachment_file_id=letter.attachment_file_id,
            attachment_filename=attach.name if attach else None,
            reply_to_letter_id=letter.reply_to_letter_id,
            notes=letter.notes,
            created_by_id=letter.created_by_id,
            assigned_to_id=letter.assigned_to_id,
            created_at=letter.created_at,
            updated_at=letter.updated_at,
            routings=routing_responses,
            attachments=cls.list_attachments(db, user.organization_id, letter.id, user),
            reply_count=reply_count,
        )

    @classmethod
    def list_letters(
        cls,
        db: Session,
        user: User,
        direction: Optional[LetterDirection] = None,
        status_filter: Optional[LetterStatus] = None,
        confidentiality: Optional[LetterConfidentiality] = None,
        urgency: Optional[LetterUrgency] = None,
        department_id: Optional[uuid.UUID] = None,
        ethiopian_year: Optional[int] = None,
        search: Optional[str] = None,
        is_overdue: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LetterResponse]:
        """
        List letters with multi-field search and RBAC access filtering.
        """
        query = db.query(LetterRegistry).filter(
            LetterRegistry.organization_id == user.organization_id,
        )

        if direction:
            query = query.filter(LetterRegistry.direction == direction)
        if status_filter:
            query = query.filter(LetterRegistry.status == status_filter)
        if confidentiality:
            query = query.filter(LetterRegistry.confidentiality == confidentiality)
        if urgency:
            query = query.filter(LetterRegistry.urgency == urgency)
        if department_id:
            query = query.filter(LetterRegistry.department_id == department_id)
        if ethiopian_year:
            query = query.filter(LetterRegistry.ethiopian_year == ethiopian_year)

        today = date.today()
        if is_overdue is True:
            query = query.filter(
                LetterRegistry.due_date_gc < today,
                LetterRegistry.status.notin_([LetterStatus.ARCHIVED, LetterStatus.DISPATCHED]),
            )
        elif is_overdue is False:
            query = query.filter(
                or_(
                    LetterRegistry.due_date_gc >= today,
                    LetterRegistry.status.in_([LetterStatus.ARCHIVED, LetterStatus.DISPATCHED]),
                )
            )

        if search and search.strip():
            raw_s = search.strip()
            norm_s = LocalizationService.normalize_amharic(raw_s)
            term = f"%{norm_s}%"
            raw_term = f"%{raw_s}%"
            query = query.filter(
                or_(
                    LetterRegistry.reference_number.ilike(raw_term),
                    LetterRegistry.external_reference_number.ilike(raw_term),
                    LetterRegistry.subject.ilike(raw_term),
                    LetterRegistry.subject.ilike(term),
                    LetterRegistry.sender_entity.ilike(raw_term),
                    LetterRegistry.recipient_entity.ilike(raw_term),
                )
            )

        letters = query.order_by(LetterRegistry.created_at.desc()).offset(offset).limit(limit).all()

        results = []
        for l in letters:
            # RBAC check
            if not cls.check_letter_access(l, user, db):
                continue

            dept = db.query(Department).filter(Department.id == l.department_id).first() if l.department_id else None
            attach = db.query(FileItem).filter(FileItem.id == l.attachment_file_id).first() if l.attachment_file_id else None

            days_remaining = None
            overdue_flag = False
            if l.due_date_gc and l.status not in (LetterStatus.ARCHIVED, LetterStatus.DISPATCHED):
                days_remaining = (l.due_date_gc - today).days
                overdue_flag = days_remaining < 0

            results.append(
                LetterResponse(
                    id=l.id,
                    organization_id=l.organization_id,
                    department_id=l.department_id,
                    department_name=dept.name if dept else None,
                    reference_number=l.reference_number,
                    external_reference_number=l.external_reference_number,
                    direction=l.direction,
                    status=l.status,
                    confidentiality=l.confidentiality,
                    urgency=l.urgency,
                    delivery_method=l.delivery_method,
                    subject=l.subject,
                    sender_entity=l.sender_entity,
                    sender_contact=l.sender_contact,
                    recipient_entity=l.recipient_entity,
                    recipient_contact=l.recipient_contact,
                    cc_entities=l.cc_entities,
                    date_ec=l.date_ec,
                    date_gc=l.date_gc,
                    ethiopian_year=l.ethiopian_year,
                    due_date_gc=l.due_date_gc,
                    due_date_ec=l.due_date_ec,
                    is_overdue=overdue_flag,
                    days_remaining=days_remaining,
                    approved_at_gc=l.approved_at_gc,
                    approved_by_id=l.approved_by_id,
                    rejected_at_gc=l.rejected_at_gc,
                    rejected_by_id=l.rejected_by_id,
                    rejection_reason=l.rejection_reason,
                    dispatched_at_gc=l.dispatched_at_gc,
                    dispatched_at_ec=l.dispatched_at_ec,
                    dispatched_by_id=l.dispatched_by_id,
                    attachment_file_id=l.attachment_file_id,
                    attachment_filename=attach.name if attach else None,
                    reply_to_letter_id=l.reply_to_letter_id,
                    notes=l.notes,
                    created_by_id=l.created_by_id,
                    assigned_to_id=l.assigned_to_id,
                    created_at=l.created_at,
                    updated_at=l.updated_at,
                )
            )
        return results

    @classmethod
    def get_analytics_summary(cls, db: Session, user: User) -> LetterAnalyticsSummary:
        """
        Produce high-level corporate letter registry analytics for management dashboards.
        """
        all_letters = db.query(LetterRegistry).filter(
            LetterRegistry.organization_id == user.organization_id,
        ).all()

        today = date.today()

        total = 0
        inward = 0
        outward = 0
        memos = 0
        pending_approval = 0
        dispatched = 0
        received = 0
        archived = 0
        urgent_open = 0
        overdue_sla = 0
        confidential = 0
        dept_counts: Dict[str, int] = {}
        urgency_counts: Dict[str, int] = {}

        # Preload department names
        depts = db.query(Department).filter(Department.organization_id == user.organization_id).all()
        dept_map = {d.id: d.name for d in depts}

        for l in all_letters:
            if not cls.check_letter_access(l, user, db):
                continue

            total += 1
            if l.direction == LetterDirection.INWARD:
                inward += 1
            elif l.direction == LetterDirection.OUTWARD:
                outward += 1
            elif l.direction == LetterDirection.INTERNAL_MEMO:
                memos += 1

            if l.status == LetterStatus.PENDING_APPROVAL:
                pending_approval += 1
            elif l.status == LetterStatus.DISPATCHED:
                dispatched += 1
            elif l.status == LetterStatus.RECEIVED:
                received += 1
            elif l.status == LetterStatus.ARCHIVED:
                archived += 1

            if l.urgency in (LetterUrgency.URGENT, LetterUrgency.VERY_URGENT) and l.status not in (LetterStatus.ARCHIVED, LetterStatus.DISPATCHED):
                urgent_open += 1

            if l.due_date_gc and l.due_date_gc < today and l.status not in (LetterStatus.ARCHIVED, LetterStatus.DISPATCHED):
                overdue_sla += 1

            if l.confidentiality in (LetterConfidentiality.CONFIDENTIAL, LetterConfidentiality.STRICTLY_CONFIDENTIAL):
                confidential += 1

            d_name = dept_map.get(l.department_id, "General") if l.department_id else "General"
            dept_counts[d_name] = dept_counts.get(d_name, 0) + 1

            u_val = l.urgency.value
            urgency_counts[u_val] = urgency_counts.get(u_val, 0) + 1

        return LetterAnalyticsSummary(
            total_letters=total,
            inward_count=inward,
            outward_count=outward,
            memo_count=memos,
            pending_approval_count=pending_approval,
            dispatched_count=dispatched,
            received_count=received,
            archived_count=archived,
            urgent_open_count=urgent_open,
            overdue_sla_count=overdue_sla,
            confidential_count=confidential,
            by_department=dept_counts,
            by_urgency=urgency_counts,
        )

    @classmethod
    def to_attachment_response(cls, att: LetterAttachment) -> LetterAttachmentResponse:
        ec_date = format_ethiopian_date(att.created_at.date()) if att.created_at else None
        return LetterAttachmentResponse(
            id=att.id,
            letter_id=att.letter_id,
            file_id=att.file_id,
            file_name=att.file_item.name if att.file_item else "Document",
            mime_type=att.file_item.mime_type if att.file_item else None,
            size_bytes=att.file_item.size_bytes if att.file_item else 0,
            attachment_type=att.attachment_type,
            notes=att.notes,
            attached_by_name=att.attached_by.full_name if att.attached_by else None,
            created_at=att.created_at,
            ec_created_at=ec_date,
        )

    @classmethod
    def attach_drive_file(
        cls,
        db: Session,
        org_id: uuid.UUID,
        letter_id: uuid.UUID,
        file_id: uuid.UUID,
        attachment_type: str,
        notes: Optional[str],
        actor: User,
    ) -> LetterAttachmentResponse:
        """
        Attaches a file from Personal or Company Drive to an official letter.
        Supports PRIMARY_SIGNED_PDF, SUPPORTING_DOCUMENT, and ANNEX.
        """
        CapabilityService.verify_organization_write_access(db, org_id)

        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == org_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ደብዳቤው አልተገኘም (Letter not found)")

        if not cls.check_letter_access(letter, actor, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ይህን ደብዳቤ የማየት ፈቃድ የለዎትም (Access denied to letter)")

        from app.services.storage_service import StorageService, DriveAccessDeniedError
        try:
            file_item = StorageService.get_item(db, org_id, file_id, actor)
        except DriveAccessDeniedError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ይህን ፋይል የማያያዝ ፈቃድ የለዎትም (Access denied to file)")

        if file_item.is_folder:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="አቃፊዎችን (Folders) ለደብዳቤ ማያያዝ አይቻልም")

        # Check existing attachment
        existing = db.query(LetterAttachment).filter(
            LetterAttachment.letter_id == letter.id,
            LetterAttachment.file_id == file_item.id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ይህ ፋይል ቀደም ሲል ለደብዳቤው ተያይዟል (File is already attached to this letter)")

        att = LetterAttachment(
            organization_id=org_id,
            letter_id=letter.id,
            file_id=file_item.id,
            attachment_type=attachment_type,
            notes=notes.strip() if notes else None,
            attached_by_id=actor.id,
        )
        db.add(att)

        if attachment_type == "PRIMARY_SIGNED_PDF":
            letter.attachment_file_id = file_item.id

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.CONFIG_CHANGE,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={"action": "ATTACH_FILE", "file_name": file_item.name, "type": attachment_type},
        )
        db.add(audit)
        db.commit()
        db.refresh(att)

        return cls.to_attachment_response(att)

    @classmethod
    def list_attachments(
        cls,
        db: Session,
        org_id: uuid.UUID,
        letter_id: uuid.UUID,
        actor: User,
    ) -> List[LetterAttachmentResponse]:
        """Lists all files attached to a letter."""
        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == org_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ደብዳቤው አልተገኘም (Letter not found)")

        if not cls.check_letter_access(letter, actor, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        attachments = db.query(LetterAttachment).filter(
            LetterAttachment.letter_id == letter.id,
            LetterAttachment.organization_id == org_id,
        ).order_by(LetterAttachment.created_at.asc()).all()

        return [cls.to_attachment_response(a) for a in attachments]

    @classmethod
    def delete_attachment(
        cls,
        db: Session,
        org_id: uuid.UUID,
        letter_id: uuid.UUID,
        attachment_id: uuid.UUID,
        actor: User,
    ) -> bool:
        """Removes an attachment from a letter."""
        CapabilityService.verify_organization_write_access(db, org_id)

        letter = db.query(LetterRegistry).filter(
            LetterRegistry.id == letter_id,
            LetterRegistry.organization_id == org_id,
        ).first()
        if not letter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ደብዳቤው አልተገኘም (Letter not found)")

        if not cls.check_letter_access(letter, actor, db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        att = db.query(LetterAttachment).filter(
            LetterAttachment.id == attachment_id,
            LetterAttachment.letter_id == letter.id,
        ).first()
        if not att:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ተያያዥ ሰነድ አልተገኘም (Attachment not found)")

        if letter.attachment_file_id == att.file_id:
            letter.attachment_file_id = None

        db.delete(att)

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.CONFIG_CHANGE,
            target_type="LETTER",
            target_id=letter.id,
            target_name=letter.reference_number,
            details={"action": "REMOVE_ATTACHMENT", "attachment_id": str(attachment_id)},
        )
        db.add(audit)
        db.commit()
        return True
