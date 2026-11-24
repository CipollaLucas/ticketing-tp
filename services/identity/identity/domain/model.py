"""Identity domain policies, independent of FastAPI, SQLAlchemy and Pydantic."""
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    CUSTOMER = "customer"
    EVENT_OWNER = "event_owner"
    ADMINISTRATOR = "administrator"


class IdentityFault(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Principal:
    id: UUID
    username: str
    display_name: str
    role: Role


def ensure_owner(actor: Principal, owner_id: UUID) -> None:
    if actor.id != owner_id and actor.role != Role.ADMINISTRATOR:
        raise IdentityFault(403, "Resource belongs to another user")


def ensure_administrator(actor: Principal) -> None:
    if actor.role != Role.ADMINISTRATOR:
        raise IdentityFault(403, "Administrator role required")


def validate_role_change(actor: Principal, target: UUID) -> None:
    ensure_administrator(actor)
    if actor.id == target:
        raise IdentityFault(409, "Cannot change your own role")
