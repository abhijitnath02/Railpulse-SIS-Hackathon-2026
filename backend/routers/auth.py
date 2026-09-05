"""
/auth endpoints (item 9 — Auth + role-based access control).

Standard OAuth2 "password" flow so Swagger UI's built-in Authorize button
works out of the box: POST username+password as form data to /auth/token,
get a JWT back, send it as `Authorization: Bearer <token>` on subsequent
requests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from typing import List

from ..auth import verify_password, create_access_token, get_current_user, require_role
from ..schemas import Token, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")

    token = create_access_token(username=user.username, role=user.role)
    return Token(access_token=token, role=user.role, username=user.username)


@router.get("/me", response_model=UserOut)
def read_current_user(user: models.User = Depends(get_current_user)):
    return UserOut(username=user.username, role=user.role, is_active=user.is_active)


@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), _admin: models.User = Depends(require_role("admin"))):
    """Admin-only endpoint (item 9's third role tier). Deliberately trivial
    — its purpose in this codebase is to be a concrete example of a route
    that only 'admin' can reach, for the RBAC demo/tests to exercise."""
    return [UserOut(username=u.username, role=u.role, is_active=u.is_active) for u in db.query(models.User).all()]
