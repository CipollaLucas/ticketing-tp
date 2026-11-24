"""Ticketing-owned DB. No Events or Identity tables, imports or foreign keys."""
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Uuid, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ticketing_service.domain import GateCommand, GateState
from ticketing_service.settings import settings


class Base(DeclarativeBase):
    pass


class SaleGateRow(Base):
    __tablename__ = "sale_gates"
    __table_args__ = (
        CheckConstraint("state IN ('closed','open')", name="valid_sale_gate_state"),
        CheckConstraint("version >= 0", name="nonnegative_sale_gate_version"),
        CheckConstraint("event_revision >= 0", name="nonnegative_metadata_revision"),
    )
    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    state: Mapped[str] = mapped_column(String(8), nullable=False, default="closed")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class GateCommandRow(Base):
    __tablename__ = "sale_gate_commands"
    command_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("sale_gates.event_id"), nullable=False,
    )
    action: Mapped[str] = mapped_column(String(8), nullable=False)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_state: Mapped[str] = mapped_column(String(8), nullable=False)
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)


engine = create_engine(settings.database_url, pool_pre_ping=True)


class SqlAlchemyGateUnitOfWork:
    def __init__(self, session: Session):
        self.db = session

    def previous_command(self, command: GateCommand) -> tuple[GateCommand, GateState] | None:
        row = self.db.get(GateCommandRow, command.command_id)
        if row is None:
            return None
        old = GateCommand(
            row.command_id, row.event_id, row.action, row.expected_version,
            row.event_revision,
        )
        result = GateState(row.event_id, row.result_state, row.result_version,
                           row.result_revision)
        return old, result

    def lock_gate(self, event_id: UUID) -> GateState | None:
        row = self.db.scalar(
            select(SaleGateRow).where(SaleGateRow.event_id == event_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if row is None:
            return None
        return GateState(row.event_id, row.state, row.version, row.event_revision)

    def save(self, command: GateCommand, state: GateState) -> None:
        row = self.db.get(SaleGateRow, state.event_id)
        assert row is not None
        row.state = state.state
        row.version = state.version
        row.event_revision = state.event_revision
        self.db.add(GateCommandRow(
            command_id=command.command_id, event_id=command.event_id,
            action=command.action, expected_version=command.expected_version,
            event_revision=command.event_revision, result_state=state.state,
            result_version=state.version, result_revision=state.event_revision,
        ))

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
