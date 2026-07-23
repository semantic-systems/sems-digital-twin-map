"""
Admin-only user management. Every route requires the caller to be an admin
(get_current_admin → 403 otherwise). The first admin is bootstrapped from the CLI
(scripts/create_user.py --admin); from there admins can create/manage others here.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import get_current_admin, hash_password
from ..db import User, UserAdmission, UserReportState, UserSession, get_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class UserOut(BaseModel):
    username: str
    active: bool
    is_admin: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    # All optional — only the provided fields change.
    password: str | None = Field(default=None, min_length=8)
    is_admin: bool | None = None
    active: bool | None = None


def _to_out(u: User) -> UserOut:
    return UserOut(username=u.username, active=u.active, is_admin=u.is_admin, created_at=u.created_at)


@router.get("/users", response_model=list[UserOut])
def list_users(
    _admin: str = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    users = db.query(User).order_by(User.username).all()
    return [_to_out(u) for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: CreateUserRequest,
    _admin: str = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        active=True,
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.patch("/users/{username}", response_model=UserOut)
def update_user(
    username: str,
    body: UpdateUserRequest,
    admin: str = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user: User | None = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="No such user")

    # Self-protection: an admin can't lock themselves out (demote or deactivate
    # their own account). Changing your own password is fine.
    if username == admin:
        if body.is_admin is False:
            raise HTTPException(status_code=400, detail="You cannot remove your own admin role")
        if body.active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.active is not None:
        user.active = body.active
        # Deactivating revokes existing sessions immediately.
        if not body.active:
            db.query(UserSession).filter(UserSession.username == username).delete()

    db.commit()
    db.refresh(user)
    return _to_out(user)


@router.delete("/users/{username}")
def delete_user(
    username: str,
    admin: str = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    if username == admin:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    user: User | None = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(status_code=404, detail="No such user")

    # Remove the account and all state keyed by its username (these tables key on
    # the username string, not a FK to users, so they must be cleaned explicitly).
    db.query(UserSession).filter(UserSession.username == username).delete()
    db.query(UserAdmission).filter(UserAdmission.username == username).delete()
    db.query(UserReportState).filter(UserReportState.username == username).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}
