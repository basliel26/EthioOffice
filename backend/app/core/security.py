from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
import bcrypt
from jose import jwt
from app.core.config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a bcrypt hash for the provided plaintext password."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt)
    return hashed.decode("utf-8")


def create_access_token(
    subject: Union[str, Any],
    organization_id: Union[str, Any],
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Creates a signed JWT access token for authenticated users."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "org_id": str(organization_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decodes and validates a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None
