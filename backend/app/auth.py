"""Identity routes and shared authorization rules for the first increment."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AuthSession, Role, User
from app.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Identity"])
password_hasher = PasswordHash.recommended()
# Unknown usernames still incur password verification, as documented by FastAPI.
dummy_password_hash = password_hasher.hash(token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictRequest):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9_-]+$")
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class RegisterRequest(LoginRequest):
    password: SecretStr = Field(min_length=12, max_length=128)
    display_name: DisplayName


class ProfileUpdate(StrictRequest):
    display_name: DisplayName


class RoleUpdate(StrictRequest):
    role: Role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    display_name: str
    role: Role


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def unauthorized(detail: str = "Invalid or expired credentials") -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def get_current_user(db: Db, credentials: Credentials) -> User:
    if credentials is None:
        raise unauthorized()
    user = db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_digest(credentials.credentials),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if user is None:
        raise unauthorized()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_administrator(user: CurrentUser) -> User:
    if user.role != Role.ADMINISTRATOR:
        raise HTTPException(403, "Administrator role required")
    return user


def require_event_owner(user: CurrentUser) -> User:
    if user.role not in (Role.EVENT_OWNER, Role.ADMINISTRATOR):
        raise HTTPException(403, "Event owner role required")
    return user


def require_owner_or_admin(user: User, owner_id: UUID) -> None:
    """Use before mutating a resource; never trust owner IDs from request bodies."""
    if user.id != owner_id and user.role != Role.ADMINISTRATOR:
        raise HTTPException(403, "Resource belongs to another user")


Administrator = Annotated[User, Depends(require_administrator)]


@router.post("/auth/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Db) -> User:
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        password_hash=password_hasher.hash(payload.password.get_secret_value()),
        role=Role.CUSTOMER.value,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists") from None
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db, response: Response) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == payload.username))
    stored_hash = user.password_hash if user else dummy_password_hash
    valid = password_hasher.verify(payload.password.get_secret_value(), stored_hash)
    if not valid or user is None:
        raise unauthorized("Invalid username or password")
    token = token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=token_digest(token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.session_ttl_seconds),
        )
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=token, expires_in=settings.session_ttl_seconds)


@router.get("/auth/me", response_model=UserResponse)
def me(user: CurrentUser) -> User:
    return user


@router.post("/auth/logout", status_code=204)
def logout(user: CurrentUser, db: Db, credentials: Credentials) -> Response:
    # Authentication above guarantees credentials exist and the session is valid.
    assert credentials is not None
    db.execute(
        delete(AuthSession).where(AuthSession.token_hash == token_digest(credentials.credentials))
    )
    db.commit()
    return Response(status_code=204)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_profile(user_id: UUID, payload: ProfileUpdate, user: CurrentUser, db: Db) -> User:
    require_owner_or_admin(user, user_id)
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    target.display_name = payload.display_name
    db.commit()
    db.refresh(target)
    return target


@router.patch("/admin/users/{user_id}/role", response_model=UserResponse)
def update_role(user_id: UUID, payload: RoleUpdate, admin: Administrator, db: Db) -> User:
    # A stable lock order serializes role changes across the current administrators.
    # Recheck the actor after waiting: another request may have revoked its role.
    db.scalars(
        select(User.id).where(User.role == Role.ADMINISTRATOR).order_by(User.id).with_for_update()
    ).all()
    db.refresh(admin)
    require_administrator(admin)
    if admin.id == user_id:
        raise HTTPException(409, "Cannot change your own role")
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    target.role = payload.role.value
    db.commit()
    db.refresh(target)
    return target
