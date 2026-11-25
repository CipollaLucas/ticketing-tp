"""Real isolated PostgreSQL purchase UoW, transactions, locking and replay."""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from alembic import command
from ticketing_service.application import change_sale_gate
from ticketing_service.domain import GateCommand
from ticketing_service.no_sales_close import ConfirmedSalesExist, close_gate_without_sales
from ticketing_service.persistence import (
    OrderItemRow,
    OrderRow,
    SaleGateRow,
    SqlAlchemyGateUnitOfWork,
    TicketRow,
    ZoneRow,
)
from ticketing_service.purchase import (
    PurchaseError,
    PurchaseIntent,
    PurchaseKeyConflict,
    TicketSelection,
)
from ticketing_service.purchase_application import purchase_tickets
from ticketing_service.purchase_persistence import SqlAlchemyPurchaseUnitOfWork

DB_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="Disposable PostgreSQL not configured")


def setup_event(engine, *, open_sales=True, capacity=4):
    event_id, zone_id = uuid4(), uuid4()
    with Session(engine) as db:
        db.add(SaleGateRow(
            event_id=event_id, state="open" if open_sales else "closed",
            version=1 if open_sales else 0, event_revision=1 if open_sales else 0,
        ))
        db.add(ZoneRow(
            id=zone_id, event_id=event_id, name="General", mode="general",
            price_minor=1200, currency="ARS", capacity=capacity, available=capacity,
        ))
        db.commit()
    return event_id, zone_id


def purchase(engine, intent, customer, key):
    with Session(engine) as db:
        return purchase_tickets(intent, customer, key, SqlAlchemyPurchaseUnitOfWork(db))


def close(engine, event):
    with Session(engine) as db:
        return change_sale_gate(
            GateCommand(uuid4(), event, "close", 1, 1),
            SqlAlchemyGateUnitOfWork(db),
        )


def state(engine, event, zone):
    with Session(engine) as db:
        gate = db.get(SaleGateRow, event)
        stock = db.get(ZoneRow, zone).available
        order_count = db.scalar(select(func.count()).select_from(OrderRow).where(
            OrderRow.event_id == event,
        ))
        ticket_count = db.scalar(
            select(func.count()).select_from(TicketRow)
            .join(OrderItemRow, TicketRow.order_item_id == OrderItemRow.id)
            .join(OrderRow, OrderItemRow.order_id == OrderRow.id)
            .where(OrderRow.event_id == event)
        )
        return gate.state, stock, order_count, ticket_count


def test_purchase_replay_and_rollback_on_insufficient_stock():
    assert DB_URL is not None
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(DB_URL)
    event, zone = setup_event(engine, capacity=2)
    customer = uuid4()
    intent = PurchaseIntent(event, (TicketSelection(zone, 2),))
    first = purchase(engine, intent, customer, "key-1")
    assert not first.replayed and len(first.order.tickets) == 2
    replay = purchase(engine, intent, customer, "key-1")
    assert replay.replayed and replay.order.id == first.order.id
    with pytest.raises(PurchaseKeyConflict):
        purchase(engine, PurchaseIntent(event, (TicketSelection(zone, 1),)), customer, "key-1")
    with pytest.raises(PurchaseError) as error:
        purchase(engine, PurchaseIntent(event, (TicketSelection(zone, 1),)), customer, "key-2")
    assert error.value.status == 409
    assert state(engine, event, zone) == ("open", 0, 1, 2)
    close(engine, event)
    assert purchase(engine, intent, customer, "key-1").replayed
    with pytest.raises(PurchaseError):
        purchase(engine, intent, uuid4(), "new-key")
    assert state(engine, event, zone) == ("closed", 0, 1, 2)
    engine.dispose()


def test_close_before_purchase_prevents_all_writes():
    assert DB_URL is not None
    engine = create_engine(DB_URL)
    event, zone = setup_event(engine)
    close(engine, event)
    with pytest.raises(PurchaseError) as error:
        purchase(engine, PurchaseIntent(event, (TicketSelection(zone, 1),)), uuid4(), "late")
    assert error.value.status == 409
    assert state(engine, event, zone) == ("closed", 4, 0, 0)
    engine.dispose()


def test_purchase_holds_same_gate_lock_until_commit_before_close():
    assert DB_URL is not None
    engine = create_engine(DB_URL, pool_size=5)
    event, zone = setup_event(engine, capacity=2)
    locked = Event()
    release = Event()

    def purchase_with_pause():
        # A session-level proxy pauses after the real purchase UoW gate row
        # has been acquired, before it releases its single DB transaction.
        class PausedUnit(SqlAlchemyPurchaseUnitOfWork):
            def allocate(self, customer_id, key, intent):
                result = super().allocate(customer_id, key, intent)
                locked.set()
                assert release.wait(timeout=10)
                return result

        with Session(engine) as db:
            return purchase_tickets(
                PurchaseIntent(event, (TicketSelection(zone, 1),)),
                uuid4(), "before-close", PausedUnit(db),
            )

    def concurrent_close():
        assert locked.wait(timeout=10)
        return close(engine, event)

    with ThreadPoolExecutor(max_workers=2) as pool:
        purchase_future = pool.submit(purchase_with_pause)
        close_future = pool.submit(concurrent_close)
        assert locked.wait(timeout=10)
        release.set()
        result = purchase_future.result(timeout=15)
        closed = close_future.result(timeout=15)
    assert not result.replayed and closed.state == "closed"
    assert state(engine, event, zone) == ("closed", 1, 1, 1)
    engine.dispose()


def test_parallel_same_customer_and_key_allocates_once():
    assert DB_URL is not None
    engine = create_engine(DB_URL, pool_size=5)
    event, zone = setup_event(engine, capacity=2)
    customer = uuid4()
    intent = PurchaseIntent(event, (TicketSelection(zone, 1),))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(purchase, engine, intent, customer, "same-key") for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert {result.order.id for result in results} == {results[0].order.id}
    assert sorted(result.replayed for result in results) == [False, True]
    assert state(engine, event, zone) == ("open", 1, 1, 1)
    engine.dispose()


def no_sales_close(engine, event):
    with Session(engine) as db:
        return close_gate_without_sales(
            GateCommand(uuid4(), event, "close", 1, 1),
            SqlAlchemyGateUnitOfWork(db),
        )


def test_no_sales_close_before_purchase_rejects_new_order():
    assert DB_URL is not None
    engine = create_engine(DB_URL)
    event, zone = setup_event(engine)
    assert no_sales_close(engine, event).state == "closed"
    with pytest.raises(PurchaseError):
        purchase(
            engine, PurchaseIntent(event, (TicketSelection(zone, 1),)),
            uuid4(), "late-after-no-sales-close",
        )
    assert state(engine, event, zone) == ("closed", 4, 0, 0)
    engine.dispose()


def test_purchase_commits_first_no_sales_close_refuses_and_keeps_gate_open():
    assert DB_URL is not None
    engine = create_engine(DB_URL, pool_size=5)
    event, zone = setup_event(engine, capacity=2)
    locked = Event()
    release = Event()

    class PausedPurchase(SqlAlchemyPurchaseUnitOfWork):
        def allocate(self, customer_id, key, intent):
            result = super().allocate(customer_id, key, intent)
            locked.set()
            assert release.wait(timeout=10)
            return result

    def purchase_before_close():
        with Session(engine) as db:
            return purchase_tickets(
                PurchaseIntent(event, (TicketSelection(zone, 1),)),
                uuid4(), "purchase-first", PausedPurchase(db),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        buyer = pool.submit(purchase_before_close)
        assert locked.wait(timeout=10)
        closer = pool.submit(no_sales_close, engine, event)
        release.set()
        assert not buyer.result(timeout=15).replayed
        with pytest.raises(ConfirmedSalesExist):
            closer.result(timeout=15)
    assert state(engine, event, zone) == ("open", 1, 1, 1)
    engine.dispose()
