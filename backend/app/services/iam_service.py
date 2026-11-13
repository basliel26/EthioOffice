import re
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User
from app.models.user_session import UserSession
from app.models.audit import AuditLog, AuditAction

REFRESH_TOKEN_EXPIRE_DAYS = 30
DUMMY_BCRYPT_HASH = "$2b$12$e8xL27K/G6s7m71vU.8U1u777777777777777777777777777777."


class PasswordValidationError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class TokenInvalidError(Exception):
    pass


class IAMService:
    @staticmethod
    def validate_password_strength(password: str) -> None:
        """
        Enforces corporate password strength rules:
        - At least 8 characters
        - At least one letter and at least one number
        """
        if len(password) < 8:
            raise PasswordValidationError("የይለፍ ቃል ቢያንስ 8 ፊደላት ወይም ቁጥሮች መሆን አለበት (Password must be at least 8 characters)")
        if not re.search(r"[A-Za-z]", password):
            raise PasswordValidationError("የይለፍ ቃል ቢያንስ አንድ ፊደል ማካተት አለበት (Password must contain at least one letter)")
        if not re.search(r"\d", password):
            raise PasswordValidationError("የይለፍ ቃል ቢያንስ አንድ ቁጥር ማካተት አለበት (Password must contain at least one digit)")

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def authenticate(
        cls,
        db: Session,
        email: str,
        password: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[User, str, str]:
        """
        Authenticates an employee with timing-attack prevention, issues a short-lived
        JWT access token and a cryptographically secure 30-day refresh token.
        """
        clean_email = email.lower().strip()
        user = db.query(User).filter(User.email == clean_email).first()

        # Timing attack mitigation: always execute bcrypt check even if user doesn't exist
        password_to_check = user.hashed_password if user else DUMMY_BCRYPT_HASH
        is_valid = verify_password(password, password_to_check)

        if not user or not is_valid:
            raise AuthenticationError("የተሳሳተ ኢሜይል ወይም የይለፍ ቃል (Incorrect email or password)")

        if not user.is_active:
            raise AuthenticationError("ይህ የተጠቃሚ አካውንት ተዘግቷል (User account is deactivated)")

        # Enterprise Multi-Tenant Status Check: Verify organization is not suspended
        if hasattr(user.organization, "status") and str(user.organization.status.value if hasattr(user.organization.status, "value") else user.organization.status) == "SUSPENDED":
            raise AuthenticationError("የድርጅቱ አገልግሎት ለጊዜው ታግዷል፤ እባክዎ የስርዓት አስተዳዳሪውን ያነጋግሩ (Organization subscription is suspended. Please contact your administrator)")

        # Generate refresh token
        raw_refresh_token = secrets.token_urlsafe(32)
        token_hash = cls._hash_token(raw_refresh_token)

        # Create session record
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            client_ip=client_ip,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(session)

        # Audit log login
        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            ip_address=client_ip,
            details={"user_agent": user_agent[:128] if user_agent else None}
        )
        db.add(audit)
        db.commit()

        # Generate access token
        access_token = create_access_token(
            subject=user.id,
            organization_id=user.organization_id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role)
        )

        return user, access_token, raw_refresh_token

    @classmethod
    def rotate_refresh_token(
        cls,
        db: Session,
        refresh_token: str,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Rotates the refresh token: revokes the previous session and creates a fresh session.
        Prevents replay attacks.
        """
        token_hash = cls._hash_token(refresh_token)
        now = datetime.now(timezone.utc)

        session = db.query(UserSession).filter(
            UserSession.token_hash == token_hash,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).first()

        if not session:
            raise TokenInvalidError("የማይታወቅ ወይም ጊዜው ያለፈበት የመታደሻ ቶከን (Invalid or expired refresh token)")

        user = db.query(User).filter(User.id == session.user_id, User.is_active == True).first()
        if not user:
            raise TokenInvalidError("ተጠቃሚው አልተገኘም (User not found or inactive)")

        # Revoke old session (Rotation)
        session.is_revoked = True

        # Issue new refresh token
        new_raw_token = secrets.token_urlsafe(32)
        new_session = UserSession(
            user_id=user.id,
            token_hash=cls._hash_token(new_raw_token),
            client_ip=client_ip or session.client_ip,
            user_agent=user_agent or session.user_agent,
            expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(new_session)
        db.commit()

        new_access_token = create_access_token(
            subject=user.id,
            organization_id=user.organization_id,
            role=user.role.value if hasattr(user.role, "value") else str(user.role)
        )

        return new_access_token, new_raw_token

    @classmethod
    def revoke_session(cls, db: Session, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id
        ).first()
        if session:
            session.is_revoked = True
            db.commit()
            return True
        return False

    @classmethod
    def revoke_all_sessions(cls, db: Session, user_id: uuid.UUID) -> int:
        count = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False
        ).update({"is_revoked": True})
        db.commit()
        return count

    @classmethod
    def list_active_sessions(cls, db: Session, user_id: uuid.UUID) -> List[UserSession]:
        now = datetime.now(timezone.utc)
        return db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked == False,
            UserSession.expires_at > now
        ).order_by(UserSession.last_active_at.desc()).all()

    @classmethod
    def change_password(
        cls,
        db: Session,
        user: User,
        current_password: str,
        new_password: str
    ) -> bool:
        """
        Validates existing password, checks strength of new password, updates hash,
        and revokes all active sessions to secure the account.
        """
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("የአሁኑ የይለፍ ቃል የተሳሳተ ነው (Current password is incorrect)")

        cls.validate_password_strength(new_password)

        user.hashed_password = get_password_hash(new_password)
        cls.revoke_all_sessions(db, user.id)
        db.commit()
        return True
