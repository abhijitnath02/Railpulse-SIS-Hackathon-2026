"""
Seeds the three demo RBAC accounts on startup, idempotently (skips any
username that already exists). Called once from main.py's startup.

Demo credentials (change/remove before any real deployment):
    admin    / admin123    (role=admin)
    operator / operator123 (role=operator)
    viewer   / viewer123   (role=viewer)
"""
from sqlalchemy.orm import Session

from . import models
from .auth import hash_password

DEMO_USERS = [
    {"username": "admin", "password": "admin123", "role": "admin"},
    {"username": "operator", "password": "operator123", "role": "operator"},
    {"username": "viewer", "password": "viewer123", "role": "viewer"},
]


def seed_demo_users(db: Session) -> None:
    for spec in DEMO_USERS:
        existing = db.query(models.User).filter(models.User.username == spec["username"]).first()
        if existing:
            continue
        db.add(models.User(
            username=spec["username"],
            hashed_password=hash_password(spec["password"]),
            role=spec["role"],
            is_active=True,
        ))
    db.commit()
