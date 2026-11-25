"""PostgreSQL gate provisioning with INSERT ON CONFLICT DO NOTHING."""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ticketing_service.domain import GateState, SaleState
from ticketing_service.persistence import SaleGateRow
from ticketing_service.provision import validate_provision_state


class SqlAlchemyGateProvisionUnitOfWork:
    def __init__(self, db: Session):
        self.db = db

    def ensure_closed_gate(self, event_id: UUID) -> GateState:
        self.db.execute(
            insert(SaleGateRow)
            .values(
                event_id=event_id,
                state="closed",
                version=0,
                event_revision=0,
            )
            .on_conflict_do_nothing(index_elements=[SaleGateRow.event_id]),
        )
        row = self.db.scalar(
            select(SaleGateRow)
            .where(SaleGateRow.event_id == event_id)
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        assert row is not None
        state = GateState(
            event_id=row.event_id,
            state=cast(SaleState, row.state),
            version=row.version,
            event_revision=row.event_revision,
        )
        validate_provision_state(state, event_id)
        return state

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
