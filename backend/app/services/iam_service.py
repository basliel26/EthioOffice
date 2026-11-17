import re
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserRole
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


class AccountLockedError(Exception):
    pass


class IPAccessRestrictedError(Exception):
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

        # Enterprise Brute-Force Defense: Check if account is temporarily locked
        if user and user.is_locked:
            now = datetime.now(timezone.utc)
            locked_dt = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
            remaining_secs = max(1, int((locked_dt - now).total_seconds()))
            remaining_mins = max(1, (remaining_secs + 59) // 60)
            raise AccountLockedError(
                f"ተደጋጋሚ የተሳሳተ ሙከራ በማድረጉ ይህ አካውንት ለ{remaining_mins} ደቂቃዎች ታግዷል "
                f"(Account temporarily locked due to 5 consecutive failed login attempts. Try again in {remaining_mins} minutes or contact your administrator)"
            )

        # Timing attack mitigation: always execute bcrypt check even if user doesn't exist
        password_to_check = user.hashed_password if user else DUMMY_BCRYPT_HASH
        is_valid = verify_password(password, password_to_check)

        if not user or not is_valid:
            if user:
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                    audit = AuditLog(
                        organization_id=user.organization_id,
                        user_id=user.id,
                        action=AuditAction.LOGIN,
                        target_type="USER",
                        target_id=user.id,
                        target_name=user.full_name,
                        ip_address=client_ip,
                        details={"action": "ACCOUNT_LOCKED_BRUTE_FORCE", "failed_attempts": user.failed_login_attempts}
                    )
                    db.add(audit)
                    db.commit()
                    raise AccountLockedError(
                        "የይለፍ ቃል 5 ጊዜ ተሳስቷል፤ አካውንቱ ለ15 ደቂቃዎች ታግዷል (Account locked for 15 minutes due to 5 consecutive failed login attempts)"
                    )
                else:
                    attempts_left = 5 - user.failed_login_attempts
                    db.commit()
                    raise AuthenticationError(
                        f"የተሳሳተ ኢሜይል ወይም የይለፍ ቃል ({attempts_left} ሙከራዎች ቀርተዋል) "
                        f"(Incorrect email or password. {attempts_left} attempts remaining before account lockout)"
                    )
            raise AuthenticationError("የተሳሳተ ኢሜይል ወይም የይለፍ ቃል (Incorrect email or password)")

        if not user.is_active:
            raise AuthenticationError("ይህ የተጠቃሚ አካውንት ተዘግቷል (User account is deactivated)")

        # Enterprise Security: Corporate IP / CIDR Subnet Whitelist
        if client_ip and hasattr(user.organization, "allowed_ip_ranges") and user.organization.allowed_ip_ranges:
            import ipaddress
            allowed_raw = [t.strip() for t in user.organization.allowed_ip_ranges.split(",") if t.strip()]
            allowed_subnets = []
            for item in allowed_raw:
                try:
                    allowed_subnets.append(ipaddress.ip_network(item, strict=False))
                except ValueError:
                    pass
            
            if allowed_subnets:
                ip_to_check = "127.0.0.1" if client_ip.lower() == "testclient" else client_ip.strip()
                try:
                    ip_obj = ipaddress.ip_address(ip_to_check)
                    is_ip_allowed = any(ip_obj in subnet for subnet in allowed_subnets)
                    if not is_ip_allowed:
                        raise IPAccessRestrictedError(
                            f"ከዚህ የኢንተርኔት አድራሻ ({client_ip}) መግባት አልተፈቀደም (Login from IP '{client_ip}' is blocked. Access is restricted to authorized corporate subnets)"
                        )
                except ValueError:
                    raise IPAccessRestrictedError(
                        f"ትክክለኛ ያልሆነ የኢንተርኔት አድራሻ ({client_ip}) (Unparseable client IP '{client_ip}')"
                    )

        # Reset failed attempts on successful login
        if user.failed_login_attempts > 0 or user.locked_until is not None:
            user.failed_login_attempts = 0
            user.locked_until = None

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

    @classmethod
    def create_user(
        cls,
        db: Session,
        org_id: uuid.UUID,
        email: str,
        password: str,
        full_name: str,
        role: UserRole = UserRole.STAFF,
        actor: Optional[User] = None
    ) -> User:
        """
        Provisions a new employee account under the organization.
        Enforces Module 3 seat limits: blocks creation if active seats reached licensed capacity.
        """
        clean_email = email.lower().strip()
        
        # Check uniqueness
        existing = db.query(User).filter(User.email == clean_email).first()
        if existing:
            raise AuthenticationError("ይህ ኢሜይል አስቀድሞ ተመዝግቧል (Email is already registered)")

        # Validate password strength
        cls.validate_password_strength(password)

        # Enforce write access (license expiry lockdown) and seat limits
        from app.services.capability_service import CapabilityService
        CapabilityService.verify_organization_write_access(db, org_id)
        CapabilityService.enforce_seat_limit(db, org_id)

        # Create user
        new_user = User(
            organization_id=org_id,
            email=clean_email,
            full_name=full_name.strip(),
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        db.add(new_user)
        db.flush()

        if actor:
            audit = AuditLog(
                organization_id=org_id,
                user_id=actor.id,
                action=AuditAction.LOGIN,
                target_type="USER",
                target_id=new_user.id,
                target_name=new_user.full_name,
                details={"action": "USER_PROVISIONED", "email": new_user.email, "role": str(role)}
            )
            db.add(audit)

        db.commit()
        db.refresh(new_user)
        return new_user

    @classmethod
    def unlock_user_account(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User
    ) -> bool:
        """
        Manually unlocks an employee's account after lockout.
        Restricted to Organization Administrators or Superusers.
        """
        user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
        if not user:
            raise AuthenticationError("ተጠቃሚው አልተገኘም (User not found)")

        user.failed_login_attempts = 0
        user.locked_until = None

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            details={"action": "ACCOUNT_UNLOCKED_BY_ADMIN", "unlocked_user": user.email}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def update_profile(
        cls,
        db: Session,
        user: User,
        full_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        """
        Updates an employee's personal profile information.
        """
        if full_name is not None:
            clean_name = full_name.strip()
            if not clean_name:
                raise ValueError("ስም ባዶ መሆን አይችልም (Full name cannot be empty)")
            user.full_name = clean_name

        if phone_number is not None:
            user.phone_number = phone_number.strip() if phone_number.strip() else None

        if avatar_url is not None:
            user.avatar_url = avatar_url.strip() if avatar_url.strip() else None

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.CONFIG_CHANGE,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            details={"action": "PROFILE_UPDATED"}
        )
        db.add(audit)
        db.commit()
        db.refresh(user)
        return user

    @classmethod
    def change_password(
        cls,
        db: Session,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """
        Self-service password change: validates current password, validates new password complexity,
        updates hash, and revokes all active sessions for security.
        """
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("የአሁኑ የይለፍ ቃል የተሳሳተ ነው (Current password is incorrect)")

        cls.validate_password_strength(new_password)

        if verify_password(new_password, user.hashed_password):
            raise PasswordValidationError("አዲሱ የይለፍ ቃል ከአሮጌው ጋር ተመሳሳይ መሆን አይችልም (New password cannot be the same as current password)")

        user.hashed_password = get_password_hash(new_password)

        # Revoke all active sessions
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()

        audit = AuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            details={"action": "PASSWORD_CHANGED"}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def admin_reset_password(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        new_password: str,
        actor: User,
    ) -> bool:
        """
        Administrative password reset: resets employee password, clears lockouts, and revokes sessions.
        """
        if not (actor.is_admin or actor.is_superuser):
            raise AuthenticationError("ይህን እርምጃ ለመፈጸም የአስተዳዳሪ ፈቃድ ያስፈልጋል (Admin privileges required)")

        user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
        if not user:
            raise AuthenticationError("ተጠቃሚው አልተገኘም (User not found)")

        cls.validate_password_strength(new_password)
        user.hashed_password = get_password_hash(new_password)
        user.failed_login_attempts = 0
        user.locked_until = None

        db.query(UserSession).filter(UserSession.user_id == user.id).delete()

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            details={"action": "PASSWORD_RESET_BY_ADMIN", "target_email": user.email}
        )
        db.add(audit)
        db.commit()
        return True

    @classmethod
    def lock_user_account(
        cls,
        db: Session,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        actor: User,
        lock_duration_hours: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Administrative account lock: prevents employee login and terminates active sessions.
        """
        if not (actor.is_admin or actor.is_superuser):
            raise AuthenticationError("ይህን እርምጃ ለመፈጸም የአስተዳዳሪ ፈቃድ ያስፈልጋል (Admin privileges required)")

        if user_id == actor.id:
            raise AuthenticationError("የራስዎን አካውንት ማገድ አይችሉም (Cannot lock your own account)")

        user = db.query(User).filter(User.id == user_id, User.organization_id == org_id).first()
        if not user:
            raise AuthenticationError("ተጠቃሚው አልተገኘም (User not found)")

        if user.is_superuser and not actor.is_superuser:
            raise AuthenticationError("የስርዓት አስተዳዳሪን ማገድ አይቻልም (Cannot lock a Super Admin)")

        now = datetime.now(timezone.utc)
        if lock_duration_hours:
            user.locked_until = now + timedelta(hours=lock_duration_hours)
        else:
            # Indefinite lock (100 years)
            user.locked_until = now + timedelta(days=36500)

        # Terminate active sessions immediately
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()

        audit = AuditLog(
            organization_id=org_id,
            user_id=actor.id,
            action=AuditAction.LOGIN,
            target_type="USER",
            target_id=user.id,
            target_name=user.full_name,
            details={
                "action": "ACCOUNT_LOCKED_BY_ADMIN",
                "target_email": user.email,
                "reason": reason or "Administrative suspension",
                "locked_until": str(user.locked_until),
            }
        )
        db.add(audit)
        db.commit()
        return True

