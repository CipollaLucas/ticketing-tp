"""SQLAlchemy adapter. All database code belongs outside the application."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Uuid, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from identity.domain.model import (
    IdentityFault,
    Principal,
    Role,
    validate_role_change,
)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('customer', 'event_owner', 'administrator')",
            name="valid_user_role",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default=Role.CUSTOMER.value)


class SessionRow(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


def principal(row: UserRow) -> Principal:
    return Principal(row.id, row.username, row.display_name, Role(row.role))


class SqlAlchemyIdentityStore:
    def __init__(self, db: Session):
        self.db = db

    def get_by_name(self, username: str) -> tuple[Principal, str] | None:
        row = self.db.scalar(select(UserRow).where(UserRow.username == username))
        return (principal(row), row.password_hash) if row is not None else None

    def get_by_id(self, user_id: UUID) -> Principal | None:
        row = self.db.get(UserRow, user_id)
        return principal(row) if row is not None else None

    def create(self, username: str, display_name: str, hashed: str) -> Principal:
        row = UserRow(username=username, display_name=display_name, password_hash=hashed)
        self.db.add(row)
        self.db.flush()
        return principal(row)

    def find_session(self, token_hash: str, now: datetime) -> Principal | None:
        row = self.db.scalar(
            select(UserRow).join(SessionRow, SessionRow.user_id == UserRow.id).where(
                SessionRow.token_hash == token_hash, SessionRow.expires_at > now,
            )
        )
        return principal(row) if row is not None else None

    def add_session(self, token_hash: str, user_id: UUID, expires_at: datetime) -> None:
        self.db.add(SessionRow(token_hash=token_hash, user_id=user_id, expires_at=expires_at))

    def remove_session(self, token_hash: str) -> None:
        self.db.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash))

    def set_display_name(self, user_id: UUID, display_name: str) -> Principal:
        row = self.db.get(UserRow, user_id)
        assert row is not None
        row.display_name = display_name
        self.db.flush()
        return principal(row)

    def change_role(self, actor_id: UUID, target_id: UUID, role: Role) -> Principal:
        # Lock current administrators in stable order (revocation-safe).
        self.db.scalars(
            select(UserRow.id).where(UserRow.role == Role.ADMINISTRATOR.value)
            .order_by(UserRow.id).with_for_update()
        ).all()
        actor = self.db.get(UserRow, actor_id, populate_existing=True)
        if actor is None:
            raise IdentityFault(401, "Invalid or expired credentials")
        validate_role_change(principal(actor), target_id)
        target = self.db.get(UserRow, target_id)
        if target is None:
            raise IdentityFault(404, "User not found")
        target.role = role.value
        self.db.flush()
        return principal(target)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
