"""Admin user CRUD and password resets."""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.audit import record_audit
from app.services.sessions import destroy_user_sessions


def list_users(session: Session) -> list[User]:
    """Return all users ordered by username."""

    return list(session.exec(select(User).order_by(User.username)).all())


def get_user(session: Session, user_id: int) -> User:
    """Fetch a user by id.

    Raises:
        NotFoundError: if the user does not exist.
    """

    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    role: UserRole,
    actor: User,
    ip: str | None = None,
) -> User:
    """Create a user (admin only at the route layer).

    Raises:
        ConflictError: if the username is taken.
    """

    existing = session.exec(
        select(User).where(User.username == username.strip())
    ).first()
    if existing is not None:
        raise ConflictError("Username already exists")

    user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        must_change_password=True,
    )
    session.add(user)
    session.flush()
    record_audit(
        session,
        action="users.create",
        user_id=actor.id,
        target=f"user:{user.username}",
        details={"role": role.value},
        ip=ip,
    )
    session.commit()
    session.refresh(user)
    return user


def update_user(
    session: Session,
    user_id: int,
    *,
    actor: User,
    role: UserRole | None = None,
    is_active: bool | None = None,
    ip: str | None = None,
) -> User:
    """Update role and/or active flag.

    Raises:
        NotFoundError: if missing.
        ForbiddenError: if an admin would lock themselves out.
    """

    user = get_user(session, user_id)
    if user.id == actor.id and is_active is False:
        raise ForbiddenError("You cannot deactivate your own account")
    if user.id == actor.id and role is not None and role != UserRole.ADMIN:
        raise ForbiddenError("You cannot remove your own admin role")

    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
        if not is_active and user.id is not None:
            destroy_user_sessions(session, user.id)

    session.add(user)
    record_audit(
        session,
        action="users.update",
        user_id=actor.id,
        target=f"user:{user.username}",
        details={"role": user.role.value, "is_active": user.is_active},
        ip=ip,
    )
    session.commit()
    session.refresh(user)
    return user


def reset_password(
    session: Session,
    user_id: int,
    *,
    new_password: str,
    actor: User,
    ip: str | None = None,
) -> User:
    """Admin password reset; forces change on next login.

    Raises:
        NotFoundError: if missing.
    """

    user = get_user(session, user_id)
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    session.add(user)
    if user.id is not None:
        destroy_user_sessions(session, user.id)
    record_audit(
        session,
        action="users.reset_password",
        user_id=actor.id,
        target=f"user:{user.username}",
        ip=ip,
    )
    session.commit()
    session.refresh(user)
    return user


def delete_user(
    session: Session,
    user_id: int,
    *,
    actor: User,
    ip: str | None = None,
) -> None:
    """Delete a user account.

    Raises:
        NotFoundError: if missing.
        ForbiddenError: if deleting yourself.
    """

    user = get_user(session, user_id)
    if user.id == actor.id:
        raise ForbiddenError("You cannot delete your own account")
    username = user.username
    if user.id is not None:
        destroy_user_sessions(session, user.id)
    session.delete(user)
    record_audit(
        session,
        action="users.delete",
        user_id=actor.id,
        target=f"user:{username}",
        ip=ip,
    )
    session.commit()
