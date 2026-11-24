"""Inbound HTTP adapter: HTTP/Pydantic never escape into domain or application."""
from datetime import UTC, datetime
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from identity.adapters.crypto import Argon2Passwords, RandomTokenGenerator
from identity.adapters.persistence import SqlAlchemyIdentityStore
from identity.application import use_cases
from identity.database import get_db
from identity.domain.model import IdentityFault, Principal, Role
from identity.settings import settings

router = APIRouter(prefix="/api/v1", tags=["Identity"])
bearer = HTTPBearer(auto_error=False)
passwords = Argon2Passwords()
tokens = RandomTokenGenerator()
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


def error_to_http(error: IdentityFault) -> HTTPException:
    return HTTPException(
        status_code=error.status, detail=error.detail,
        headers={"WWW-Authenticate": "Bearer"} if error.status == 401 else None,
    )


def current_token(credentials: Credentials) -> str:
    if credentials is None:
        raise HTTPException(401, "Invalid or expired credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    return credentials.credentials


def current_principal(token: Annotated[str, Depends(current_token)], db: Db) -> Principal:
    try:
        return use_cases.introspect(token, SqlAlchemyIdentityStore(db), datetime.now(UTC))
    except IdentityFault as error:
        raise error_to_http(error) from error


PrincipalDep = Annotated[Principal, Depends(current_principal)]


@router.post("/auth/register", response_model=UserResponse, status_code=201)
def register(payload: RegisterRequest, db: Db) -> Principal:
    try:
        return use_cases.register(
            payload.username, payload.password.get_secret_value(),
            payload.display_name, SqlAlchemyIdentityStore(db), passwords,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username already exists") from None


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db, response: Response) -> use_cases.AccessToken:
    try:
        result = use_cases.login(
            payload.username, payload.password.get_secret_value(),
            SqlAlchemyIdentityStore(db), passwords, tokens,
            datetime.now(UTC), settings.session_ttl_seconds,
        )
    except IdentityFault as error:
        raise error_to_http(error) from error
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/auth/me", response_model=UserResponse)
def me(principal: PrincipalDep) -> Principal:
    return principal


@router.post("/auth/logout", status_code=204)
def logout(token: Annotated[str, Depends(current_token)], db: Db) -> Response:
    try:
        use_cases.logout(token, SqlAlchemyIdentityStore(db), datetime.now(UTC))
    except IdentityFault as error:
        raise error_to_http(error) from error
    return Response(status_code=204)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_profile(
    user_id: UUID, payload: ProfileUpdate, principal: PrincipalDep, db: Db,
) -> Principal:
    try:
        return use_cases.update_profile(
            principal, user_id, payload.display_name, SqlAlchemyIdentityStore(db),
        )
    except IdentityFault as error:
        raise error_to_http(error) from error


@router.patch("/admin/users/{user_id}/role", response_model=UserResponse)
def update_role(
    user_id: UUID, payload: RoleUpdate, principal: PrincipalDep, db: Db,
) -> Principal:
    try:
        return use_cases.update_role(
            principal, user_id, payload.role, SqlAlchemyIdentityStore(db),
        )
    except IdentityFault as error:
        raise error_to_http(error) from error


@router.get("/internal/auth/introspect", response_model=UserResponse, tags=["Internal"])
def internal_introspect(
    token: Annotated[str, Depends(current_token)],
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")],
    db: Db,
) -> Principal:
    # Fail closed, including when a caller knows a valid customer access token.
    if internal_token is None or not compare_digest(
        internal_token.encode(), settings.identity_internal_token.encode()
    ):
        raise HTTPException(403, "Internal service credential required")
    try:
        return use_cases.introspect(token, SqlAlchemyIdentityStore(db), datetime.now(UTC))
    except IdentityFault as error:
        raise error_to_http(error) from error
