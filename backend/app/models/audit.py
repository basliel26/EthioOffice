from datetime import datetime, timezone
import enum
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class AuditAction(str, enum.Enum):
    LOGIN = "LOGIN"
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    VIEW = "VIEW"
    EDIT_EUROOFFICE = "EDIT_EUROOFFICE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    SHARE = "SHARE"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(Enum(AuditAction, name="audit_action_enum"), nullable=False, index=True)
    target_type = Column(String(30), nullable=False)  # 'FILE', 'FOLDER', 'SHARE', 'USER'
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    target_name = Column(String(255), nullable=False)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    # Relationships
    user = relationship("User")
