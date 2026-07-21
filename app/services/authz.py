from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User

CLIENT_TRANSACTION_ROLES = {"ROOT", "ADMIN", "OPERATOR"}
CLIENT_ADMIN_ROLES = {"ROOT", "ADMIN"}
BACKOFFICE_APPROVER_ROLE = "BACKOFFICE_ADMIN"


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user


def require_client_transaction_role(db: Session, user_id: int, client_id: int) -> User:
    user = get_user_or_404(db, user_id)
    if user.scope != "CLIENT" or user.client_id != client_id or user.role not in CLIENT_TRANSACTION_ROLES:
        raise HTTPException(403, "User cannot create transactions for this client")
    return user


def require_client_admin(db: Session, user_id: int, client_id: int) -> User:
    user = get_user_or_404(db, user_id)
    if user.scope != "CLIENT" or user.client_id != client_id or user.role not in CLIENT_ADMIN_ROLES:
        raise HTTPException(403, "Client admin/root permission required")
    return user


def require_backoffice_approver(db: Session, user_id: int) -> User:
    user = get_user_or_404(db, user_id)
    if user.scope != "BACKOFFICE" or user.role != BACKOFFICE_APPROVER_ROLE:
        raise HTTPException(403, "Back-office admin permission required")
    return user


def require_backoffice_operator(db: Session, user_id: int) -> User:
    """Demo operations use the same back-office role as approval.

    Production should split approval, wallet operations and broadcast permissions.
    """
    return require_backoffice_approver(db, user_id)
