"""Disposable real-HTTP purchase vs unpublish race through independent services.

Both operations start simultaneously, use separate HTTP clients and independent
PostgreSQL transactions. Either serial order is legal; a confirmed order with a
closed gate or an unpublished event is NEVER legal. No persistent DB allowed.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
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


def require_status(reply: httpx.Response, status: int, label: str) -> dict:
    assert reply.status_code == status, (
        f"{label}: wanted {status}, got {reply.status_code}: {reply.text[:150]}"
    )
    return reply.json()


def main() -> None:
    if (
        engine.url.database != "h4_ticketing_test"
        or os.environ.get("H4_DISPOSABLE_UAT") != "yes"
    ):
        raise SystemExit("REFUSED: only disposable Ticketing PostgreSQL")
    identity_url = os.environ["H3_IDENTITY_URL"]
    events_url = os.environ["H3_EVENTS_URL"]
    ticketing_url = os.environ["H4_TICKETING_URL"]
    password = os.environ["H3_TEST_PASSWORD"]
    with httpx.Client(base_url=identity_url, timeout=10, trust_env=False) as identity:
        owner = require_status(identity.post("/api/v1/auth/login", json={
            "username": "h3owner", "password": password,
        }), 200, "Owner login")["access_token"]
        customer = require_status(identity.post("/api/v1/auth/login", json={
            "username": "h3customer", "password": password,
        }), 200, "Customer login")["access_token"]

    owner_auth = {"Authorization": f"Bearer {owner}"}
    customer_auth = {"Authorization": f"Bearer {customer}"}
    start = datetime.now(UTC) + timedelta(days=8)

    # A few independent attempts exercise both valid serial outcomes without
    # relying on request arrival order or arbitrary sleeps.
    for round_no in range(8):
        with httpx.Client(base_url=events_url, timeout=10, trust_env=False) as client:
            body = {
                "name": f"H4 concurrent race {round_no}",
                "description": "Single confirmed order versus conditional close",
                "venue": "Disposable race fixture",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=2)).isoformat(),
            }
            event = require_status(client.post(
                "/api/v1/events", headers=owner_auth, json=body,
            ), 201, "Create")
            event_id = UUID(event["id"])
            require_status(client.post(
                f"/api/v1/events/{event_id}/publish", headers=owner_auth, json={},
            ), 200, "Publish")

        zone_id = uuid4()
        with Session(engine) as db:
            db.add(ZoneRow(
                id=zone_id, event_id=event_id,
                name="General", mode="general",
                price_minor=1100, currency="ARS",
                capacity=2, available=2,
            ))
            db.commit()

        ready = Barrier(3)

        def buyer(
            ready: Barrier = ready,
            event_id: UUID = event_id,
            zone_id: UUID = zone_id,
            round_no: int = round_no,
        ) -> httpx.Response:
            with httpx.Client(base_url=ticketing_url, timeout=15, trust_env=False) as cli:
                ready.wait(timeout=10)
                return cli.post(
                    f"/api/v1/events/{event_id}/orders",
                    json={"items": [{"zone_id": str(zone_id), "quantity": 1}]},
                    headers=customer_auth | {
                        "Idempotency-Key": f"concurrent-sale-{round_no}",
                    },
                )

        def closer(
            ready: Barrier = ready,
            event_id: UUID = event_id,
        ) -> httpx.Response:
            with httpx.Client(base_url=events_url, timeout=15, trust_env=False) as cli:
                ready.wait(timeout=10)
                return cli.post(
                    f"/api/v1/events/{event_id}/unpublish",
                    headers=owner_auth, json={},
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            bought_future = executor.submit(buyer)
            closed_future = executor.submit(closer)
            ready.wait(timeout=10)
            bought = bought_future.result(timeout=20)
            closed = closed_future.result(timeout=20)

        assert bought.status_code in {201, 403, 409}, (
            f"Purchase race: {bought.status_code} {bought.text[:150]}"
        )
        assert closed.status_code in {200, 409}, (
            f"Unpublish race: {closed.status_code} {closed.text[:150]}"
        )

        with Session(engine) as db:
            gate = db.get(SaleGateRow, event_id)
            zone = db.get(ZoneRow, zone_id)
            orders = db.scalars(select(OrderRow).where(
                OrderRow.event_id == event_id,
            )).all()
            tickets = db.scalar(
                select(func.count()).select_from(TicketRow).join(
                    ZoneRow, TicketRow.zone_id == ZoneRow.id,
                ).where(ZoneRow.event_id == event_id)
            )
            assert gate is not None and zone is not None
            if bought.status_code == 201:
                assert closed.status_code == 409
                assert gate.state == "open" and gate.version == 1
                assert len(orders) == 1 and orders[0].status == "confirmed"
                assert zone.available == 1 and tickets == 1
            else:
                assert closed.status_code == 200
                assert gate.state == "closed" and gate.version == 2
                assert orders == [] and zone.available == 2 and tickets == 0

        with httpx.Client(base_url=events_url, timeout=10, trust_env=False) as cli:
            detail = cli.get(f"/api/v1/events/{event_id}")
            assert detail.status_code == (200 if bought.status_code == 201 else 404)

        print(f"PASS: HTTP purchase/close race {round_no + 1}: "
              f"purchase={bought.status_code} unpublish={closed.status_code}")

    print("PASS: eight process-independent HTTP races preserve gate, orders and stock")


if __name__ == "__main__":
    main()
