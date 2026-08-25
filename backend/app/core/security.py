"""Security utilities: JWT tokens, password hashing, and token encryption."""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"


def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.ENCRYPTION_KEY.encode())


# -----------------------------------------------
# Password Hashing (Direct bcrypt for reliability)
# -----------------------------------------------
def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


# -----------------------------------------------
# JWT Tokens
# -----------------------------------------------
def create_access_token(subject: str | UUID, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": str(subject), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str | UUID) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(subject), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def verify_access_token(token: str) -> Optional[str]:
    """Returns user_id string or None if token is invalid."""
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# -----------------------------------------------
# Third-party Token Encryption (JIRA/GitHub PATs/OAuth tokens)
# -----------------------------------------------
def encrypt_token(plaintext: str) -> str:
    """Encrypt a secret string (PAT, OAuth token) for storage in DB."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored encrypted token."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
