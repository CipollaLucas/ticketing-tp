"""Disposable cross-service UAT with a REAL confirmed Ticketing purchase.

Event is created/published via real Identity and Events HTTP. A purchase is
committed via Ticketing's existing application UoW (purchase HTTP does not
exist yet). Events unpublish must return 409 without altering sale gate,
order, ticket, inventory or public metadata. Never use persistent databases.
"""
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ticketing_service.persistence import (
    OrderRow,
    SaleGateRow,
    TicketRow,
    ZoneRow,
    engine,
)
from ticketing_service.purchase import PurchaseIntent, TicketSelection
from ticketing_service.purchase_application import purchase_tickets
from ticketing_service.purchase_persistence import SqlAlchemyPurchaseUnitOfWork


def checked(response: httpx.Response, expected: int, step: str) -> dict:
    assert response.status_code == expected, (
        f"{step}: expected {expected}, got {response.status_code}"
    )
    return response.json()


def main() -> None:
    if (
        engine.url.database != "h4_ticketing_test"
        or os.environ.get("H4_DISPOSABLE_UAT") != "yes"
    ):
        raise SystemExit("REFUSED: purchase UAT requires disposable Ticketing PostgreSQL")
    now = datetime.now(UTC)
    start = now + timedelta(days=8)
    with (
        httpx.Client(
            base_url=os.environ["H3_IDENTITY_URL"], timeout=6, trust_env=False,
        ) as identity,
        httpx.Client(
            base_url=os.environ["H3_EVENTS_URL"], timeout=6, trust_env=False,
        ) as events,
        httpx.Client(
            base_url=os.environ["H4_TICKETING_URL"], timeout=6, trust_env=False,
        ) as ticketing,
    ):
        checked(ticketing.get("/health"), 200, "Ticketing health")
        password = os.environ["H3_TEST_PASSWORD"]
        owner = checked(identity.post("/api/v1/auth/login", json={
            "username": "h3owner", "password": password,
        }), 200, "Owner login")["access_token"]
        customer = checked(identity.post("/api/v1/auth/login", json={
            "username": "h3customer", "password": password,
        }), 200, "Customer login")["access_token"]
        customer_info = checked(identity.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {customer}"},
        ), 200, "Customer identity")
        customer_id = UUID(customer_info["id"])
        owner_header = {"Authorization": f"Bearer {owner}"}
        event = checked(events.post("/api/v1/events", json={
            "name": "H4 confirmed-sale immutable event",
            "description": "Real Ticketing purchase before unpublish",
            "venue": "Disposable fixture only",
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        }, headers=owner_header), 201, "Draft creation")
        event_id = UUID(event["id"])
        published = checked(events.post(
            f"/api/v1/events/{event_id}/publish", json={}, headers=owner_header,
        ), 200, "Publish")
        assert published["status"] == "published"

        zone_id = uuid4()
        with Session(engine) as db:
            gate = db.get(SaleGateRow, event_id)
            assert gate is not None
            assert (gate.state, gate.version, gate.event_revision) == ("open", 1, 1)
            db.add(ZoneRow(
                id=zone_id, event_id=event_id, name="General",
                mode="general", price_minor=1200, currency="ARS",
                capacity=3, available=3,
            ))
            db.commit()

        intent = PurchaseIntent(event_id, (TicketSelection(zone_id, 2),))
        with Session(engine) as db:
            result = purchase_tickets(
                intent, customer_id, "h4-real-confirmed-order",
                SqlAlchemyPurchaseUnitOfWork(db),
            )
        assert not result.replayed
        assert result.order.status == "confirmed"
        assert result.order.total_minor == 2400
        assert len(result.order.tickets) == 2
        confirmed_id = result.order.id
        ticket_ids = {ticket.id for ticket in result.order.tickets}

        response = events.post(
            f"/api/v1/events/{event_id}/unpublish",
            json={}, headers=owner_header,
        )
        assert response.status_code == 409, (
            f"Sold event must reject unpublish: {response.status_code}"
        )
        response_again = events.post(
            f"/api/v1/events/{event_id}/unpublish",
            json={}, headers=owner_header,
        )
        assert response_again.status_code == 409

        with Session(engine) as db:
            gate = db.get(SaleGateRow, event_id)
            zone = db.get(ZoneRow, zone_id)
            order = db.get(OrderRow, confirmed_id)
            actual_tickets = db.scalars(
                select(TicketRow).where(TicketRow.id.in_(ticket_ids))
            ).all()
            assert gate is not None
            assert (gate.state, gate.version, gate.event_revision) == ("open", 1, 1)
            assert zone is not None and zone.available == 1
            assert order is not None and order.status == "confirmed"
            assert len(actual_tickets) == 2
            assert {ticket.id for ticket in actual_tickets} == ticket_ids
            assert all(ticket.status == "valid" for ticket in actual_tickets)
            assert db.scalar(select(func.count()).select_from(OrderRow).where(
                OrderRow.event_id == event_id,
            )) == 1
        detail = checked(events.get(
            f"/api/v1/events/{event_id}",
        ), 200, "Event remains public")
        assert detail["status"] == "published"
        with Session(engine) as db:
            replay = purchase_tickets(
                intent, customer_id, "h4-real-confirmed-order",
                SqlAlchemyPurchaseUnitOfWork(db),
            )
        assert replay.replayed and replay.order.id == confirmed_id
        assert len(replay.order.tickets) == 2

    print("PASS: Identity and Events over real HTTP; confirmed purchase via real Ticketing UoW")
    print("PASS: HTTP unpublish refuses confirmed orders twice with 409")
    print("PASS: Ticketing sale gate remains open v1 and Events remains published")
    print("PASS: order, two valid tickets and remaining capacity preserved")
    print("PASS: historical purchase replay allocates no additional tickets")


if __name__ == "__main__":
    main()
