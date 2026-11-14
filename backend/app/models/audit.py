from datetime import datetime, timezone
import enum
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Enum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base


class AuditAction(str, enum.Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    USER_CREATE = "USER_CREATE"
    USER_UPDATE = "USER_UPDATE"
    USER_LOCK = "USER_LOCK"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    SECURITY_ALERT = "SECURITY_ALERT"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    EXPORT = "EXPORT"
    LICENSE_CHANGE = "LICENSE_CHANGE"

    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    VIEW = "VIEW"
    EDIT_EUROOFFICE = "EDIT_EUROOFFICE"
    DELETE = "DELETE"
    RESTORE = "RESTORE"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    SHARE = "SHARE"

    LETTER_REGISTER = "LETTER_REGISTER"
    LETTER_DISPATCH = "LETTER_DISPATCH"
    LETTER_APPROVE = "LETTER_APPROVE"
    LETTER_REJECT = "LETTER_REJECT"
    LETTER_ROUTE = "LETTER_ROUTE"
    LETTER_ARCHIVE = "LETTER_ARCHIVE"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    action = Column(Enum(AuditAction, name="audit_action_enum"), nullable=False, index=True)
    target_type = Column(String(30), nullable=False)  # 'FILE', 'FOLDER', 'SHARE', 'USER', 'LETTER', 'ORGANIZATION', 'LICENSE'
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    target_name = Column(String(255), nullable=False)
    details = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)

    severity = Column(String(20), default="INFO", nullable=False, index=True)  # 'INFO', 'WARNING', 'CRITICAL'
    status = Column(String(20), default="SUCCESS", nullable=False, index=True)    # 'SUCCESS', 'FAILED', 'DENIED'

    # Cryptographic Hash Chaining (Blockchain-Light Non-Repudiation)
    prev_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
    )

    # Relationships
    user = relationship("User")
    organization = relationship("Organization")


import hashlib
import json
from sqlalchemy import event, text

@event.listens_for(AuditLog, "before_insert")
def audit_log_before_insert(mapper, connection, target):
    """
    Automated SQLAlchemy hook guaranteeing that ANY AuditLog row inserted into the database
    is cryptographically hashed and chained to its predecessor, even when added directly.
    """
    if not target.created_at:
        target.created_at = datetime.now(timezone.utc)

    if not target.prev_hash or not target.entry_hash:
        prev_h = "GENESIS"
        if target.organization_id:
            row = connection.execute(
                text("SELECT entry_hash FROM audit_logs WHERE organization_id = :org_id ORDER BY id DESC LIMIT 1"),
                {"org_id": target.organization_id}
            ).fetchone()
            if row and row[0]:
                prev_h = row[0]

        target.prev_hash = prev_h

        act_str = target.action.value if hasattr(target.action, "value") else str(target.action)
        payload_str = json.dumps(target.details or {}, sort_keys=True)
        raw_str = (
            f"{target.prev_hash}|{str(target.organization_id) if target.organization_id else ''}|{act_str}|{target.target_type}|"
            f"{str(target.target_id) if target.target_id else ''}|{target.target_name}|{payload_str}|"
            f"{target.created_at.isoformat()}"
        )
        target.entry_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

