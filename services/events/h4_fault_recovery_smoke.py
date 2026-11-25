"""Real multi-service acknowledgement-loss UAT over isolated PostgreSQLs.

The fault proxy allows Ticketing to commit OPEN/CLOSE but replies 503 once.
Events must persist the same command and recover via HTTP replay. The runner
never connects to a persistent database or enables regular deployment flags.
"""
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from events_service.persistence import (
    EventRow,
    PublicationIntentRow,
    UnpublishIntentRow,
    engine,
)

TOKEN = os.environ["H4_SALES_TOKEN"]


def gate(client: httpx.Client, event_id: UUID) -> dict:
    reply = client.get(
        f"/api/v1/internal/sales/gates/{event_id}",
        headers={"X-Internal-Service-Token": TOKEN},
    )
    assert reply.status_code == 200, f"Gate state: {reply.status_code}"
    return reply.json()


def main() -> None:
    if engine.url.database != "h3_events_test" or os.getenv("H4_DISPOSABLE_UAT") != "yes":
        raise SystemExit("REFUSED: only disposable Events PostgreSQL")
    with (
        httpx.Client(
            base_url=os.environ["H3_IDENTITY_URL"], timeout=10, trust_env=False,
        ) as identity,
        httpx.Client(
            base_url=os.environ["H3_EVENTS_URL"], timeout=10, trust_env=False,
        ) as events,
        httpx.Client(
            base_url=os.environ["H4_TICKETING_URL"], timeout=10, trust_env=False,
        ) as ticketing,
    ):
        login = identity.post("/api/v1/auth/login", json={
            "username": "h3owner", "password": os.environ["H3_TEST_PASSWORD"],
        })
        assert login.status_code == 200
        bearer = login.json()["access_token"]
        start = datetime.now(UTC) + timedelta(days=6)
        created = events.post(
            "/api/v1/events",
            headers={"Authorization": f"Bearer {bearer}"},
            json={
                "name": "Fault injection: lost ACK",
                "description": "Ticketing commits but Events never sees first successful response",
                "venue": "Disposable UAT",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=2)).isoformat(),
            },
        )
        assert created.status_code == 201, f"Create: {created.status_code}"
        event_id = UUID(created.json()["id"])

        headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Request-ID": "h4-lost-publish-ack",
        }
        route = f"/api/v1/events/{event_id}/publish"
        uncertain = events.post(route, headers=headers, json={})
        assert uncertain.status_code == 503, (
            f"Lost publish ACK must not return 200: {uncertain.status_code}"
        )
        with Session(engine) as db:
            row = db.get(EventRow, event_id)
            intent = db.get(PublicationIntentRow, event_id)
            assert row is not None and row.status == "published" and row.revision == 1
            assert intent is not None and intent.phase == "metadata_published"
            publication_id = intent.command_id
        opened = gate(ticketing, event_id)
        assert (opened["state"], opened["version"], opened["event_revision"]) == (
            "open", 1, 1,
        )

        recovered = events.post(route, headers=headers, json={})
        assert recovered.status_code == 200, (
            f"Publish recovery: {recovered.status_code} {recovered.text[:140]}"
        )
        assert gate(ticketing, event_id) == opened
        with Session(engine) as db:
            assert db.get(PublicationIntentRow, event_id).command_id == publication_id

        close_headers = {
            "Authorization": f"Bearer {bearer}",
            "X-Request-ID": "h4-lost-unpublish-ack",
        }
        unpublish_route = f"/api/v1/events/{event_id}/unpublish"
        uncertain = events.post(unpublish_route, headers=close_headers, json={})
        assert uncertain.status_code == 503, (
            f"Lost close ACK must not return 200: {uncertain.status_code}"
        )
        closed = gate(ticketing, event_id)
        assert (closed["state"], closed["version"], closed["event_revision"]) == (
            "closed", 2, 2,
        )
        with Session(engine) as db:
            event = db.get(EventRow, event_id)
            intent = db.get(UnpublishIntentRow, event_id)
            assert event is not None and event.status == "published"
            assert intent is not None and intent.phase == "prepared"
            close_id = intent.command_id
        recovered = events.post(unpublish_route, headers=close_headers, json={})
        assert recovered.status_code == 200, (
            f"Unpublish recovery: {recovered.status_code} {recovered.text[:140]}"
        )
        assert recovered.json()["status"] == "draft"
        assert gate(ticketing, event_id) == closed
        with Session(engine) as db:
            event = db.get(EventRow, event_id)
            intent = db.get(UnpublishIntentRow, event_id)
            assert event is not None and event.revision == 2 and event.status == "draft"
            assert intent is not None and intent.phase == "completed"
            assert intent.command_id == close_id

    print("PASS: Ticketing OPEN committed, first ACK hidden; Events 503 then replay 200")
    print("PASS: durable publication command and gate version unchanged on retry")
    print("PASS: Ticketing CLOSE committed, first ACK hidden; Events remains published")
    print("PASS: durable close command replays to draft without a second close")


if __name__ == "__main__":
    main()
