import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class LetterDirection(str, enum.Enum):
    INWARD = "INWARD"      # ወደ ድርጅቱ የገባ ደብዳቤ
    OUTWARD = "OUTWARD"    # ከድርጅቱ የወጣ ደብዳቤ


class LetterStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    RECEIVED = "RECEIVED"
    ARCHIVED = "ARCHIVED"


class LetterRegistry(Base):
    __tablename__ = "letter_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    reference_number = Column(String(100), nullable=False, index=True)  # የደብዳቤ ቁጥር e.g., 'EO/FIN/2018/142'
    direction = Column(Enum(LetterDirection, name="letter_direction_enum"), nullable=False, index=True)
    status = Column(Enum(LetterStatus, name="letter_status_enum"), default=LetterStatus.RECEIVED, nullable=False, index=True)
    
    subject = Column(String(500), nullable=False, index=True)  # የደብዳቤው ርዕስ
    sender_entity = Column(String(255), nullable=False)        # ላኪ (ድርጅት / ክፍል / ግለሰብ)
    recipient_entity = Column(String(255), nullable=False)     # ተቀባይ (ድርጅት / ክፍል / ግለሰብ)
    
    # Dates in both Ethiopian and Gregorian calendars
    date_ec = Column(String(30), nullable=False)               # ቀን በኢትዮጵያ አቆጣጠር (e.g., '15/02/2018 ዓ.ም')
    date_gc = Column(Date, nullable=False, index=True)         # Gregorian Date
    
    # Document attachment
    attachment_file_id = Column(UUID(as_uuid=True), ForeignKey("file_items.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="letter_records")
    attachment_file = relationship("FileItem")
    created_by = relationship("User", foreign_keys=[created_by_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
