"""PostgreSQL evidence for the temporary single-authority purchase boundary.

All tables live in the disposable schema provided by postgres_engine.
The active Legacy and independent Identity databases are never used.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event as Signal
from time import monotonic, sleep

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Event, Order, Role, Ticket, User, Zone
from app.ticketing_core.adapters.outbound.sqlalchemy_purchase import SqlAlchemyPurchaseUnitOfWork
from app.ticketing_core.application.ports import PurchaseError
from app.ticketing_core.application.purchase_tickets import purchase_tickets
from app.ticketing_core.domain.purchase import PurchaseIntent, TicketSelection
from test_postgres import postgres_engine as postgres_engine  # noqa: PLC0414


def setup_purchase(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        customer = User(
            username="authority_buyer", display_name="Buyer",
            password_hash="unused", role=Role.CUSTOMER.value,
        )
        owner = User(
            username="authority_owner", display_name="Owner",
            password_hash="unused", role=Role.EVENT_OWNER.value,
        )
        db.add_all([customer, owner])
        db.flush()
        start = datetime.now(UTC) + timedelta(days=5)
        event = Event(
            owner_id=owner.id, name="Authority Test", description="Test event",
            venue="Venue", start_at=start, end_at=start + timedelta(hours=2),
            status="published",
        )
        db.add(event)
        db.flush()
        zone = Zone(
            event_id=event.id, name="General", mode="general",
            price_minor=500, currency="ARS", capacity=2, available=2,
        )
        db.add(zone)
        db.flush()
        customer_id, zone_id, event_id = customer.id, zone.id, event.id
        db.commit()
    intent = PurchaseIntent(
        event_id=event_id,
        items=(TicketSelection(zone_id, 1, ()),),
    )
    return customer_id, zone_id, intent


def run_purchase(engine, customer_id, intent, key, ready=None):
    with Session(engine) as db:
        # A recognizable backend connection for the concurrent lock observation.
        db.execute(text("SET application_name = 'ticketing-authority-race'"))
        if ready is not None:
            ready.set()
        return purchase_tickets(
            intent, customer_id, key, SqlAlchemyPurchaseUnitOfWork(db),
        )


def test_revoke_before_acquiring_customer_lock_blocks_purchase(postgres_engine):
    customer_id, zone_id, intent = setup_purchase(postgres_engine)
    started = Signal()

    # Same transaction holds the customer role lock and commits the revocation
    # before the waiting purchase can pass its first authorization gate.
    with Session(postgres_engine) as revoker, ThreadPoolExecutor(max_workers=1) as pool:
        user = revoker.scalar(
            select(User).where(User.id == customer_id).with_for_update()
        )
        assert user is not None
        future = pool.submit(
            run_purchase, postgres_engine, customer_id, intent, "same-key", started,
        )
        try:
            assert started.wait(timeout=5)
            deadline = monotonic() + 5
            blocked = False
            while monotonic() < deadline:
                with postgres_engine.connect() as observer:
                    blocked = observer.scalar(text(
                        "SELECT COUNT(*) FROM pg_stat_activity "
                        "WHERE application_name = 'ticketing-authority-race' "
                        "AND wait_event_type = 'Lock'"
                    )) > 0
                if blocked:
                    break
                sleep(0.02)
            assert blocked, "Purchase did not wait for the user role lock"
            user.role = Role.EVENT_OWNER.value
            revoker.commit()
            with pytest.raises(PurchaseError) as denied:
                future.result(timeout=5)
            assert denied.value.status == 403
        finally:
            revoker.rollback()

    with Session(postgres_engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 0
        assert db.scalar(select(func.count()).select_from(Ticket)) == 0
        assert db.get(Zone, zone_id).available == 2
        # Restoring role is an explicit new transaction. A rejected key is reusable.
        db.get(User, customer_id).role = Role.CUSTOMER.value
        db.commit()
    first = run_purchase(postgres_engine, customer_id, intent, "same-key")
    assert first.replayed is False
    replay = run_purchase(postgres_engine, customer_id, intent, "same-key")
    assert replay.replayed is True
    assert replay.order.id == first.order.id
    with Session(postgres_engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(Ticket)) == 1
        assert db.get(Zone, zone_id).available == 1


def test_role_revocation_denies_even_an_idempotent_replay(postgres_engine):
    customer_id, zone_id, intent = setup_purchase(postgres_engine)
    first = run_purchase(postgres_engine, customer_id, intent, "replay-key")
    assert first.replayed is False
    with Session(postgres_engine) as db:
        db.get(User, customer_id).role = Role.EVENT_OWNER.value
        db.commit()
    with pytest.raises(PurchaseError) as denied:
        run_purchase(postgres_engine, customer_id, intent, "replay-key")
    assert denied.value.status == 403
    with Session(postgres_engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(Ticket)) == 1
        assert db.get(Zone, zone_id).available == 1
