"""H5 customer ticket queries: isolation, pagination, authorization, historical reads."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ticketing_service.customer_tickets_http import (
    query_customer_tickets,
    ticket_reader_admission,
)
from ticketing_service.main import app
from ticketing_service.persistence import (
    Base,
    OrderItemRow,
    OrderRow,
    TicketRow,
    ZoneRow,
)
from ticketing_service.purchase_admission import (
    PurchaseAdmissionDenied,
    PurchaseAdmissionUnavailable,
    VerifiedCustomer,
)
from ticketing_service.purchase_http import session_scope
from ticketing_service.settings import settings


class IdentityStub:
    def __init__(self, customer_id):
        self.customer_id = customer_id
        self.failure = None

    def customer(self, token, request_id=None):
        if self.failure is not None:
            raise self.failure
        return VerifiedCustomer(self.customer_id)


@pytest.fixture
def scenario(monkeypatch):
    db_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(db_engine)
    owner_id, outsider_id, event_id, zone_id = (uuid4() for _ in range(4))
    with Session(db_engine) as db:
        db.add(
            ZoneRow(
                id=zone_id,
                event_id=event_id,
                name="General",
                mode="general",
                price_minor=1000,
                currency="ARS",
                capacity=10,
                available=7,
            )
        )
        for customer in (owner_id, outsider_id):
            order_id, item_id = uuid4(), uuid4()
            db.add(
                OrderRow(
                    id=order_id,
                    customer_id=customer,
                    event_id=event_id,
                    idempotency_key=str(uuid4()),
                    request_hash="0" * 64,
                    total_minor=1000,
                    currency="ARS",
                    status="confirmed",
                    created_at=datetime.now(UTC),
                )
            )
            db.flush()
            db.add(
                OrderItemRow(
                    id=item_id,
                    order_id=order_id,
                    zone_id=zone_id,
                    quantity=1,
                    unit_price_minor=1000,
                    subtotal_minor=1000,
                )
            )
            db.flush()
            db.add(
                TicketRow(
                    id=uuid4(),
                    order_item_id=item_id,
                    zone_id=zone_id,
                    seat_id=None,
                    status="valid",
                )
            )
        db.commit()

    stub = IdentityStub(owner_id)
    monkeypatch.setattr(settings, "purchases_enabled", False)
    app.dependency_overrides[ticket_reader_admission] = lambda: stub

    def session_override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[session_scope] = session_override
    try:
        with TestClient(app) as client:
            yield client, stub, owner_id, outsider_id, db_engine
    finally:
        app.dependency_overrides.clear()
        db_engine.dispose()


def test_customer_only_sees_own_tickets_even_when_purchases_off(scenario):
    client, _, owner, outsider, engine = scenario
    response = client.get("/api/v1/me/tickets", headers={"Authorization": "Bearer valid"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["limit"] == 20 and payload["offset"] == 0
    with Session(engine) as db:
        assert query_customer_tickets(db, outsider, 20, 0).total == 1
        assert query_customer_tickets(db, owner, 1, 1).items == []


def test_authentication_and_dependency_fail_closed(scenario):
    client, stub, *_ = scenario
    assert client.get("/api/v1/me/tickets").status_code == 401
    stub.failure = PurchaseAdmissionDenied("revoked")
    assert (
        client.get(
            "/api/v1/me/tickets",
            headers={"Authorization": "Bearer revoked"},
        ).status_code
        == 403
    )
    stub.failure = PurchaseAdmissionUnavailable("offline")
    assert (
        client.get(
            "/api/v1/me/tickets",
            headers={"Authorization": "Bearer valid"},
        ).status_code
        == 503
    )


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_invalid_pagination_is_422(scenario, query):
    client, *_ = scenario
    assert (
        client.get(
            "/api/v1/me/tickets?" + query,
            headers={"Authorization": "Bearer valid"},
        ).status_code
        == 422
    )
