"""
Auth core: password hashing, JWT issuance/verification, and FastAPI
dependencies for role-based access control (RBAC).

Roles: "viewer" (read-only), "operator" (can trigger simulated delay
events / alerts), "admin" (operator + user management / admin-only
endpoints). Roles are hierarchical for the purposes of `require_role`:
admin can do anything operator or viewer can do, operator can do anything
viewer can do.

Password hashing uses stdlib hashlib.pbkdf2_hmac (SHA-256, 260k iterations,
random per-user salt) rather than passlib/bcrypt, so this file has zero
extra dependencies beyond PyJWT — deliberate, since the rest of this repo
already asks a hackathon judge to `pip install -r requirements.txt` once.

JWT_SECRET_KEY should be set via environment variable in any real
deployment; a fallback dev-only secret is used so the demo works out of
the box, with a loud warning if it's ever used outside DEBUG.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from . import models

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = "dev-only-insecure-secret-do-not-use-in-production"
    print(
        "[auth] WARNING: JWT_SECRET_KEY not set in environment — using an "
        "insecure hardcoded dev secret. Set JWT_SECRET_KEY before any real "
        "deployment."
    )

ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# --- Password hashing ---------------------------------------------------

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Returns 'salt_hex$hash_hex'. PBKDF2-HMAC-SHA256, 260,000 iterations
    (OWASP's 2023 minimum recommendation for PBKDF2-SHA256)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return hmac.compare_digest(expected.hex(), digest_hex)


# --- JWT ------------------------------------------------------------------

def create_access_token(username: str, role: str, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# --- FastAPI dependencies --------------------------------------------------

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    payload = decode_access_token(token)
    username = payload.get("sub")
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


def require_role(minimum_role: str):
    """Dependency factory: require_role("operator") allows operator or
    admin, blocks viewer. require_role("admin") allows admin only."""
    if minimum_role not in ROLE_RANK:
        raise ValueError(f"Unknown role: {minimum_role}")

    def _dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if ROLE_RANK.get(user.role, -1) < ROLE_RANK[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role '{minimum_role}' or higher (you are '{user.role}')",
            )
        return user

    return _dependency
