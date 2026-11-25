"""Live H4 contract: Identity -> Events -> Ticketing, three separate PostgreSQLs.

Never run against a non-disposable database. Invoked solely from the H4
tmpfs Docker Compose overlay. No credentials or access tokens are printed.
"""
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from events_service.persistence import EventRow, engine


def login(client: httpx.Client, name: str, password: str) -> str:
    reply = client.post("/api/v1/auth/login", json={
        "username": name, "password": password,
    })
    assert reply.status_code == 200, f"Identity login: {reply.status_code}"
    return str(reply.json()["access_token"])


def gate(client: httpx.Client, event: str, token: str) -> dict:
    response = client.get(
        f"/api/v1/internal/sales/gates/{event}",
        headers={"X-Internal-Service-Token": token},
    )
    assert response.status_code == 200, f"Gate read: {response.status_code}"
    return response.json()


def post(events: httpx.Client, event_id: str, action: str, bearer: str) -> httpx.Response:
    return events.post(
        f"/api/v1/events/{event_id}/{action}",
        headers={"Authorization": f"Bearer {bearer}", "X-Request-ID": "h4-live-contract"},
        json={},
    )


def main() -> None:
    if engine.url.database != "h3_events_test":
        raise SystemExit("REFUSED: live UAT requires disposable Events database")
    password = os.environ["H3_TEST_PASSWORD"]
    secret = os.environ["H4_SALES_TOKEN"]
    now = datetime.now(UTC)
    start = now + timedelta(days=10)
    payload = {
        "name": "H4 live three-service event",
        "description": "End-to-end published metadata and conditional gate close",
        "venue": "Disposable venue",
        "start_at": start.isoformat(),
        "end_at": (start + timedelta(hours=2)).isoformat(),
    }

    with (
        httpx.Client(base_url=os.environ["H3_IDENTITY_URL"], timeout=6, trust_env=False) as identity,
        httpx.Client(base_url=os.environ["H3_EVENTS_URL"], timeout=6, trust_env=False) as events,
        httpx.Client(base_url=os.environ["H4_TICKETING_URL"], timeout=6, trust_env=False) as ticketing,
    ):
        owner = login(identity, "h3owner", password)
        customer = login(identity, "h3customer", password)
        first = events.post(
            "/api/v1/events", json=payload,
            headers={"Authorization": f"Bearer {owner}"},
        )
        assert first.status_code == 201, f"Create: {first.status_code} {first.text[:120]}"
        event_id = str(UUID(first.json()["id"]))
        assert first.json()["status"] == "draft"
        assert gate(ticketing, event_id, secret)["state"] == "closed"
        assert post(events, event_id, "publish", customer).status_code == 403
        assert gate(ticketing, event_id, secret)["state"] == "closed"

        published = post(events, event_id, "publish", owner)
        assert published.status_code == 200, f"Publish: {published.status_code} {published.text[:120]}"
        assert published.json()["status"] == "published"
        assert len(published.json()) == 10
        opened = gate(ticketing, event_id, secret)
        assert (opened["state"], opened["version"], opened["event_revision"]) == ("open", 1, 1)
        assert post(events, event_id, "publish", owner).status_code == 200
        assert gate(ticketing, event_id, secret) == opened
        assert events.get(f"/api/v1/events/{event_id}").status_code == 200

        unpub = post(events, event_id, "unpublish", owner)
        assert unpub.status_code == 200, f"Unpublish: {unpub.status_code} {unpub.text[:120]}"
        assert unpub.json()["status"] == "draft"
        assert len(unpub.json()) == 10
        closed = gate(ticketing, event_id, secret)
        assert (closed["state"], closed["version"], closed["event_revision"]) == ("closed", 2, 2)
        assert events.get(f"/api/v1/events/{event_id}").status_code == 404
        assert post(events, event_id, "unpublish", owner).status_code == 200
        assert gate(ticketing, event_id, secret) == closed

        republished = post(events, event_id, "publish", owner)
        assert republished.status_code == 200, (
            f"Republish: {republished.status_code} {republished.text[:120]}"
        )
        final = gate(ticketing, event_id, secret)
        assert (final["state"], final["version"], final["event_revision"]) == ("open", 3, 3)
        with Session(engine) as db:
            row = db.get(EventRow, UUID(event_id))
            assert row is not None
            assert row.status == "published" and row.revision == 3
            assert db.scalar(select(EventRow.id).where(EventRow.id == UUID(event_id))) is not None

        print("PASS: independent Identity owner/customer authorization over real HTTP")
        print("PASS: publish + idempotent replay, Ticketing CAS open v1")
        print("PASS: no-sales unpublish + idempotent replay, Ticketing CAS close v2")
        print("PASS: republish advances revision and reopens at Ticketing CAS v3")
        print("PASS: Events public detail follows publication state; UUID cross-context only")


if __name__ == "__main__":
    main()
