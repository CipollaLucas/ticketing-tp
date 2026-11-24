"""Identity use cases, entirely independent of HTTP and ORM."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID

from identity.application.ports import IdentityStore, Passwords, TokenGenerator
from identity.domain.model import IdentityFault, Principal, Role, ensure_owner


@dataclass(frozen=True)
class AccessToken:
    access_token: str
    expires_in: int
    token_type: str = "bearer"


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def register(
    username: str, password: str, display_name: str,
    store: IdentityStore, passwords: Passwords,
) -> Principal:
    try:
        principal = store.create(username, display_name, passwords.hash(password))
        store.commit()
        return principal
    except Exception:
        store.rollback()
        raise


def login(
    username: str, password: str, store: IdentityStore,
    passwords: Passwords, tokens: TokenGenerator, now: datetime, ttl: int,
) -> AccessToken:
    found = store.get_by_name(username)
    if found is None:
        passwords.dummy_verify(password)
        raise IdentityFault(401, "Invalid username or password")
    principal, hashed = found
    if not passwords.verify(password, hashed):
        raise IdentityFault(401, "Invalid username or password")
    value = tokens.new_token()
    try:
        store.add_session(token_digest(value), principal.id, now + timedelta(seconds=ttl))
        store.commit()
    except Exception:
        store.rollback()
        raise
    return AccessToken(value, ttl)


def introspect(token: str, store: IdentityStore, now: datetime) -> Principal:
    principal = store.find_session(token_digest(token), now)
    if principal is None:
        raise IdentityFault(401, "Invalid or expired credentials")
    return principal


def logout(token: str, store: IdentityStore, now: datetime) -> None:
    introspect(token, store, now)
    try:
        store.remove_session(token_digest(token))
        store.commit()
    except Exception:
        store.rollback()
        raise


def update_profile(
    actor: Principal, user_id: UUID, display_name: str, store: IdentityStore,
) -> Principal:
    ensure_owner(actor, user_id)
    if store.get_by_id(user_id) is None:
        raise IdentityFault(404, "User not found")
    try:
        result = store.set_display_name(user_id, display_name)
        store.commit()
        return result
    except Exception:
        store.rollback()
        raise


def update_role(
    actor: Principal, user_id: UUID, role: Role, store: IdentityStore,
) -> Principal:
    # Adapter locks administrator rows and rechecks role after wait.
    try:
        result = store.change_role(actor.id, user_id, role)
        store.commit()
        return result
    except Exception:
        store.rollback()
        raise
