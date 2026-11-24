from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_inventory_postgres import seed_inventory
from test_postgres import postgres_engine as postgres_engine  # noqa: PLC0414

from alembic import command
from app.auth import Credentials, Db, get_current_user, token_digest
from app.database import Base, get_db
from app.models import AuthSession, Event, Order, OrderItem, Seat, Ticket, User, Zone
from app.purchasing import router


def sale(engine, capacity=1):
    eid = seed_inventory(engine)
    with Session(engine) as db:
        db.get(Event, eid).status = "published"
        zone = Zone(event_id=eid, name="General", mode="general", capacity=capacity,
                    available=capacity, price_minor=2147483647, currency="ARS")
        numbered = Zone(event_id=eid, name="Numbered", mode="numbered",
                        price_minor=100, currency="ARS")
        db.add_all([zone, numbered])
        db.flush()
        seat = Seat(zone_id=numbered.id, label="A1")
        db.add(seat)
        for i in range(20):
            user = User(username=f"buyer_{i}", display_name="Buyer", password_hash="unused",
                        role="customer")
            db.add(user)
            db.flush()
            db.add(AuthSession(token_hash=token_digest(f"buyer-token-{i}"), user_id=user.id,
                               expires_at=datetime.now(UTC) + timedelta(hours=1)))
        db.commit()
        return eid, zone.id, numbered.id, seat.id


def test_app(engine, barrier=None):
    app = FastAPI()
    app.include_router(router)

    def session():
        with Session(engine) as db:
            yield db

    def synchronized_auth(db: Db, credentials: Credentials):
        user = get_current_user(db, credentials)
        if barrier is not None:
            barrier.wait(timeout=15)
        return user

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = synchronized_auth
    return app


# Helper factory, not an additional pytest test.
test_app.__test__ = False


def request_purchase(app, eid, zid, index=0, key="key", seat=None, quantity=1):
    with TestClient(app) as client:
        return client.post("/api/v1/orders", headers={
            "Authorization": f"Bearer buyer-token-{index}", "Idempotency-Key": key},
            json={"event_id": str(eid), "items": [{"zone_id": str(zid), "quantity": quantity,
                   "seat_ids": [str(seat)] if seat else []}]})


@pytest.mark.parametrize("numbered", [False, True])
def test_last_place_concurrent(postgres_engine, numbered):
    eid, general, zone, seat = sale(postgres_engine)
    app = test_app(postgres_engine, Barrier(2))

    def buy(index):
        return request_purchase(app, eid, zone if numbered else general, index=index,
                                seat=seat if numbered else None).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(buy, range(2))) == [201, 409]
    with Session(postgres_engine) as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 1
        assert db.scalar(select(func.count()).select_from(Ticket)) == 1
        assert db.get(Zone, general).available == (1 if numbered else 0)


@pytest.mark.parametrize("collision", [False, True])
def test_idempotency_concurrent(postgres_engine, collision):
    eid, zid, _, _ = sale(postgres_engine, capacity=5)
    app = test_app(postgres_engine, Barrier(2))

    def buy(index):
        return request_purchase(app, eid, zid, quantity=1 + (index if collision else 0))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(buy, range(2)))
    assert sorted(r.status_code for r in results) == ([201, 409] if collision else [200, 201])
    if not collision:
        assert results[0].json() == results[1].json()
    with Session(postgres_engine) as db:
        orders = db.scalars(select(Order)).all()
        assert len(orders) == 1
        sold = db.scalar(select(func.sum(OrderItem.quantity)))
        assert db.get(Zone, zid).available == 5 - sold
        assert db.scalar(select(func.count()).select_from(Ticket)) == sold


def test_initial_stress_twenty_buyers_five_places(postgres_engine):
    eid, zid, _, _ = sale(postgres_engine, capacity=5)
    app = test_app(postgres_engine, Barrier(10))
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(
            lambda i: request_purchase(app, eid, zid, index=i).status_code, range(20)))
    assert results.count(201) == 5 and results.count(409) == 15
    with Session(postgres_engine) as db:
        assert db.get(Zone, zid).available == 0
        assert db.scalar(select(func.count()).select_from(Order)) == 5
        assert db.scalar(select(func.count()).select_from(Ticket)) == 5
        assert db.scalar(select(func.sum(Order.total_minor))) == 5 * 2147483647


def test_postgres_rollback_after_stock_retry(postgres_engine):
    eid, zid, _, _ = sale(postgres_engine)
    app = test_app(postgres_engine)

    def failure(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO TICKETS"):
            raise RuntimeError("Injected emission failure")

    event.listen(postgres_engine, "before_cursor_execute", failure)
    try:
        with pytest.raises(RuntimeError, match="Injected emission failure"):
            request_purchase(app, eid, zid)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", failure)
    with Session(postgres_engine) as db:
        assert db.get(Zone, zid).available == 1
        for model in [Order, OrderItem, Ticket]:
            assert db.scalar(select(func.count()).select_from(model)) == 0
    assert request_purchase(app, eid, zid).status_code == 201


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_purchase_migration_constraints(backend, request, tmp_path):
    engine = request.getfixturevalue("postgres_engine") if backend == "postgres" else create_engine(
        f"sqlite:///{tmp_path / 'purchase.db'}")
    if backend == "sqlite":
        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    eid, zid, numbered, sid = sale(engine)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        connection.rollback()
        command.downgrade(config, "0003_inventory")
        command.upgrade(config, "head")
    app = test_app(engine)
    response = request_purchase(app, eid, numbered, seat=sid)
    assert response.status_code == 201, response.text
    with Session(engine) as db:
        ticket = db.scalar(select(Ticket))
        with pytest.raises(IntegrityError):
            db.add(Ticket(order_item_id=ticket.order_item_id, zone_id=numbered, seat_id=sid))
            db.commit()
        db.rollback()
        # FK composite rejects seat assigned to a different zone/item.
        with pytest.raises(IntegrityError):
            db.add(Ticket(order_item_id=ticket.order_item_id, zone_id=zid, seat_id=sid))
            db.commit()
        db.rollback()
        original = db.scalar(select(Order))
        with pytest.raises(IntegrityError):
            db.add(Order(customer_id=original.customer_id, event_id=eid,
                         idempotency_key=original.idempotency_key, request_hash="f"*64,
                         total_minor=0, currency="ARS"))
            db.commit()
        db.rollback()
    if backend == "sqlite":
        engine.dispose()


def test_purchase_racing_unpublish(postgres_engine):
    from app.events import router as events_router

    eid, zid, _, _ = sale(postgres_engine)
    app = test_app(postgres_engine, Barrier(2))
    app.include_router(events_router)

    def unpublish():
        with TestClient(app) as client:
            return client.post(f"/api/v1/events/{eid}/unpublish", json={},
                headers={"Authorization": "Bearer inventory-token"}).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        purchase = executor.submit(request_purchase, app, eid, zid)
        unpublish_result = executor.submit(unpublish)
        bought, unpublished = purchase.result().status_code, unpublish_result.result()
    assert (bought, unpublished) in [(201, 409), (409, 200)]
    with Session(postgres_engine) as db:
        confirmed = bought == 201
        assert db.get(Event, eid).status == ("published" if confirmed else "draft")
        assert db.get(Zone, zid).available == (0 if confirmed else 1)
        assert db.scalar(select(func.count()).select_from(Order)) == int(confirmed)
        assert db.scalar(select(func.count()).select_from(Ticket)) == int(confirmed)
