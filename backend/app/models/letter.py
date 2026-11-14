import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Date, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class LetterDirection(str, enum.Enum):
    INWARD = "INWARD"              # ወደ ድርጅቱ የገባ ደብዳቤ (የገቢ)
    OUTWARD = "OUTWARD"            # ከድርጅቱ የወጣ ደብዳቤ (የወጪ)
    INTERNAL_MEMO = "INTERNAL_MEMO"  # የውስጥ ማስታወሻ / መሪ ማስታወሻ


class LetterStatus(str, enum.Enum):
    DRAFT = "DRAFT"                        # ረቂቅ
    PENDING_APPROVAL = "PENDING_APPROVAL"  # ለማጽደቅ የቀረበ
    APPROVED = "APPROVED"                  # የጸደቀ
    DISPATCHED = "DISPATCHED"              # የተላከ / የወጣ
    RECEIVED = "RECEIVED"                  # የተረከበ / የገባ
    REJECTED = "REJECTED"                  # ያልጸደቀ / የተመለሰ
    ARCHIVED = "ARCHIVED"                  # በማህደር የተቀመጠ


class LetterConfidentiality(str, enum.Enum):
    NORMAL = "NORMAL"                                # መደበኛ
    CONFIDENTIAL = "CONFIDENTIAL"                    # ምስጢራዊ
    STRICTLY_CONFIDENTIAL = "STRICTLY_CONFIDENTIAL"  # በጣም ምስጢራዊ


class LetterUrgency(str, enum.Enum):
    NORMAL = "NORMAL"          # መደበኛ (5 working days SLA)
    URGENT = "URGENT"          # አስቸኳይ (3 working days SLA)
    VERY_URGENT = "VERY_URGENT"  # በጣም አስቸኳይ (1 working day / 24 hr SLA)


class DeliveryMethod(str, enum.Enum):
    HAND_DELIVERY = "HAND_DELIVERY"          # በእጅ የተሰጠ
    POSTAL = "POSTAL"                        # በፖስታ ቤት
    EMAIL = "EMAIL"                          # በኢሜይል
    INTERNAL_DISPATCH = "INTERNAL_DISPATCH"  # በውስጥ መልእክተኛ
    FAX = "FAX"                              # በፋክስ


class RoutingAction(str, enum.Enum):
    FOR_ACTION = "FOR_ACTION"              # አስፈላጊው እርምጃ እንዲወሰድበት
    FOR_INFORMATION = "FOR_INFORMATION"    # ለእውቀት
    FOR_APPROVAL = "FOR_APPROVAL"          # ለማጽደቅ
    FOR_COMMENT = "FOR_COMMENT"            # አስተያየት እንዲሰጥበት
    FOR_ARCHIVE = "FOR_ARCHIVE"            # በማህደር እንዲቀመጥ


class RoutingStatus(str, enum.Enum):
    PENDING = "PENDING"              # በመጠባበቅ ላይ
    ACKNOWLEDGED = "ACKNOWLEDGED"    # የተረከቡት
    COMPLETED = "COMPLETED"          # የተጠናቀቀ


class LetterRegistry(Base):
    __tablename__ = "letter_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Official Reference Numbers
    reference_number = Column(String(100), nullable=False, index=True)  # የደብዳቤ ቁጥር e.g., 'EO/FIN/2018/0042'
    external_reference_number = Column(String(100), nullable=True, index=True)  # ላኪው የሰጠው ቁጥር (for INWARD)
    
    direction = Column(Enum(LetterDirection, name="letter_direction_enum"), nullable=False, index=True)
    status = Column(Enum(LetterStatus, name="letter_status_enum"), default=LetterStatus.RECEIVED, nullable=False, index=True)
    confidentiality = Column(Enum(LetterConfidentiality, name="letter_confidentiality_enum"), default=LetterConfidentiality.NORMAL, nullable=False, index=True)
    urgency = Column(Enum(LetterUrgency, name="letter_urgency_enum"), default=LetterUrgency.NORMAL, nullable=False, index=True)
    delivery_method = Column(Enum(DeliveryMethod, name="letter_delivery_method_enum"), nullable=True)
    
    # Core Content
    subject = Column(String(500), nullable=False, index=True)  # የደብዳቤው ርዕስ
    sender_entity = Column(String(255), nullable=False)        # ላኪ (ድርጅት / ክፍል / ግለሰብ)
    sender_contact = Column(String(255), nullable=True)
    recipient_entity = Column(String(255), nullable=False)     # ተቀባይ (ድርጅት / ክፍል / ግለሰብ)
    recipient_contact = Column(String(255), nullable=True)
    cc_entities = Column(JSONB, nullable=True)                 # ግልባጭ (CC) የተደረጉ አካላት
    
    # Dates & Calendar Sync
    date_ec = Column(String(30), nullable=False)               # ቀን በኢትዮጵያ አቆጣጠር (e.g., '15/02/2018 ዓ.ም')
    date_gc = Column(Date, nullable=False, index=True)         # Gregorian Date
    ethiopian_year = Column(Integer, nullable=True, index=True) # e.g. 2018
    due_date_gc = Column(Date, nullable=True, index=True)      # SLA Deadline (Gregorian)
    due_date_ec = Column(String(30), nullable=True)            # SLA Deadline (Ethiopian)
    
    # Approval Lifecycle Metadata
    approved_at_gc = Column(DateTime(timezone=True), nullable=True)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at_gc = Column(DateTime(timezone=True), nullable=True)
    rejected_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    # Dispatch Lifecycle Metadata
    dispatched_at_gc = Column(DateTime(timezone=True), nullable=True)
    dispatched_at_ec = Column(String(30), nullable=True)
    dispatched_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Storage & Threading
    attachment_file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="SET NULL"), nullable=True)
    reply_to_letter_id = Column(UUID(as_uuid=True), ForeignKey("letter_registry.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Ownership
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="letter_records")
    department = relationship("Department")
    attachment_file = relationship("FileItem")
    created_by = relationship("User", foreign_keys=[created_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_id])
    dispatched_by = relationship("User", foreign_keys=[dispatched_by_id])
    reply_to_letter = relationship("LetterRegistry", remote_side=[id], backref="replies")
    routings = relationship("LetterRouting", back_populates="letter", cascade="all, delete-orphan", order_by="desc(LetterRouting.transferred_at)")


class LetterSequence(Base):
    __tablename__ = "letter_sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=True, index=True)
    
    fiscal_year = Column(Integer, nullable=False, index=True)  # e.g. 2018
    counter_type = Column(String(50), nullable=False)          # 'INWARD', 'OUTWARD', 'INTERNAL_MEMO'
    current_number = Column(Integer, default=0, nullable=False)
    prefix = Column(String(50), default="EO", nullable=False)
    format_pattern = Column(String(100), default="{ORG}/{DEPT}/{YEAR}/{SEQ:04d}", nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    organization = relationship("Organization")
    department = relationship("Department")


class LetterRouting(Base):
    __tablename__ = "letter_routings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    letter_id = Column(UUID(as_uuid=True), ForeignKey("letter_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    from_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    from_department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    to_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    to_department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    transferred_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    action_required = Column(Enum(RoutingAction, name="routing_action_enum"), default=RoutingAction.FOR_ACTION, nullable=False)
    priority = Column(Enum(LetterUrgency, name="letter_urgency_enum"), default=LetterUrgency.NORMAL, nullable=False)
    instructions = Column(Text, nullable=True)
    
    status = Column(Enum(RoutingStatus, name="routing_status_enum"), default=RoutingStatus.PENDING, nullable=False, index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    response_notes = Column(Text, nullable=True)

    letter = relationship("LetterRegistry", back_populates="routings")
    organization = relationship("Organization")
    from_user = relationship("User", foreign_keys=[from_user_id])
    from_department = relationship("Department", foreign_keys=[from_department_id])
    to_user = relationship("User", foreign_keys=[to_user_id])
    to_department = relationship("Department", foreign_keys=[to_department_id])
